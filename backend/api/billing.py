from datetime import datetime, date
from decimal import Decimal
from typing import List, Sequence

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import BillingPolicy, Invoice, LateFeeTier, LedgerEntry, Owner, Payment, User
from ..schemas.schemas import (
    BillingPolicyRead,
    BillingPolicyUpdate,
    BillingSummaryRead,
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    LedgerEntryRead,
    LateFeePayload,
    PaymentCreate,
    PaymentRead,
)
from ..services.audit import audit_log
from ..services.billing import (
    apply_manual_late_fee,
    auto_apply_late_fees,
    calculate_owner_balance,
    get_or_create_billing_policy,
    record_invoice,
    record_payment,
)
from ..utils.pdf_utils import generate_reminder_notice_pdf

router = APIRouter()


def _as_decimal(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _serialize_policy(policy: BillingPolicy) -> BillingPolicyRead:
    return BillingPolicyRead(
        name=policy.name,
        grace_period_days=policy.grace_period_days,
        dunning_schedule_days=policy.dunning_schedule_days or [],
        tiers=[
            {
                "id": tier.id,
                "sequence_order": tier.sequence_order,
                "trigger_days_after_grace": tier.trigger_days_after_grace,
                "fee_type": tier.fee_type,
                "fee_amount": tier.fee_amount,
                "fee_percent": tier.fee_percent,
                "description": tier.description,
            }
            for tier in sorted(policy.tiers, key=lambda t: t.sequence_order)
        ],
    )


@router.get("/invoices", response_model=List[InvoiceRead])
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> List[Invoice]:
    applied_invoice_ids = auto_apply_late_fees(db)
    if applied_invoice_ids:
        db.commit()

    if user.has_role("HOMEOWNER"):
        owner = get_owner_for_user(db, user)
        if not owner:
            return []
        return db.query(Invoice).filter(Invoice.owner_id == owner.id).order_by(Invoice.due_date.desc()).all()
    if user.has_any_role("BOARD", "TREASURER", "SYSADMIN", "AUDITOR"):
        return db.query(Invoice).order_by(Invoice.due_date.desc()).all()
    raise HTTPException(status_code=403, detail="Role not permitted to view invoices")


@router.post("/invoices", response_model=InvoiceRead)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Invoice:
    owner = db.get(Owner, payload.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot create invoices for an archived owner.")
    payload_data = payload.dict()
    if not payload_data.get("original_amount"):
        payload_data["original_amount"] = payload_data["amount"]
    invoice = Invoice(**payload_data)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    record_invoice(db, invoice)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.invoice.create",
        target_entity_type="Invoice",
        target_entity_id=str(invoice.id),
        after=payload.dict(),
    )
    return invoice


@router.patch("/invoices/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    before = {column.name: getattr(invoice, column.name) for column in Invoice.__table__.columns}
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(invoice, key, value)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    after = {column.name: getattr(invoice, column.name) for column in Invoice.__table__.columns}
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.invoice.update",
        target_entity_type="Invoice",
        target_entity_id=str(invoice.id),
        before=before,
        after=after,
    )
    return invoice


@router.post("/invoices/{invoice_id}/late-fee", response_model=InvoiceRead)
def add_late_fee(
    invoice_id: int,
    payload: LateFeePayload,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    owner = db.get(Owner, invoice.owner_id)
    if owner and owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot modify invoices for an archived owner.")
    before_amount = invoice.amount
    updated = apply_manual_late_fee(db, invoice, _as_decimal(payload.fee_amount))
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.invoice.late_fee",
        target_entity_type="Invoice",
        target_entity_id=str(invoice.id),
        before={"amount": str(before_amount)},
        after={"amount": str(updated.amount)},
    )
    return updated


@router.post("/payments", response_model=PaymentRead)
def record_payment_endpoint(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Payment:
    owner = db.get(Owner, payload.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot record payments for an archived owner.")

    if user.has_role("HOMEOWNER"):
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != payload.owner_id:
            raise HTTPException(status_code=403, detail="May only record payments for your own account")
    elif not user.has_any_role("BOARD", "TREASURER", "SYSADMIN"):
        raise HTTPException(status_code=403, detail="Role not permitted to record payments")

    payment = Payment(**payload.dict())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    record_payment(db, payment)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="billing.payment.record",
        target_entity_type="Payment",
        target_entity_id=str(payment.id),
        after=payload.dict(),
    )
    return payment


@router.get("/ledger/{owner_id}", response_model=List[LedgerEntryRead])
def get_owner_ledger(
    owner_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[LedgerEntry]:
    owner = db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    if user.has_role("HOMEOWNER"):
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != owner_id:
            raise HTTPException(status_code=403, detail="May only view your own ledger")
    elif not user.has_any_role("BOARD", "TREASURER", "SYSADMIN", "AUDITOR"):
        raise HTTPException(status_code=403, detail="Role not permitted to view ledgers")

    return (
        db.query(LedgerEntry)
        .filter(LedgerEntry.owner_id == owner_id)
        .order_by(LedgerEntry.timestamp.desc())
        .all()
    )


@router.get("/summary", response_model=BillingSummaryRead)
def accounts_receivable_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN", "AUDITOR")),
) -> BillingSummaryRead:
    applied_invoice_ids = auto_apply_late_fees(db)
    if applied_invoice_ids:
        db.commit()

    owners = db.query(Owner).all()
    total_balance = sum((calculate_owner_balance(db, owner.id) for owner in owners), Decimal("0"))
    open_invoices = db.query(Invoice).filter(Invoice.status == "OPEN").count()
    return BillingSummaryRead(
        total_balance=total_balance,
        open_invoices=open_invoices,
        owner_count=len(owners),
    )


@router.get("/policy", response_model=BillingPolicyRead)
def read_billing_policy(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> BillingPolicyRead:
    policy = get_or_create_billing_policy(db)
    db.flush()
    return _serialize_policy(policy)


@router.put("/policy", response_model=BillingPolicyRead)
def update_billing_policy(
    payload: BillingPolicyUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> BillingPolicyRead:
    policy = get_or_create_billing_policy(db)
    policy.grace_period_days = payload.grace_period_days
    policy.dunning_schedule_days = sorted(set(payload.dunning_schedule_days))

    submitted_ids: set[int] = set()
    for tier_data in payload.tiers:
        if tier_data.id:
            tier = db.get(LateFeeTier, tier_data.id)
            if not tier or tier.policy_id != policy.id:
                raise HTTPException(status_code=404, detail=f"Late fee tier {tier_data.id} not found")
        else:
            tier = LateFeeTier(policy_id=policy.id)
        tier.sequence_order = tier_data.sequence_order
        tier.trigger_days_after_grace = tier_data.trigger_days_after_grace
        tier.fee_type = tier_data.fee_type
        tier.fee_amount = tier_data.fee_amount
        tier.fee_percent = tier_data.fee_percent
        tier.description = tier_data.description
        db.add(tier)
        db.flush()
        submitted_ids.add(tier.id)

    existing_ids = {tier.id for tier in policy.tiers}
    for tier_id in existing_ids - submitted_ids:
        tier = db.get(LateFeeTier, tier_id)
        if tier:
            db.delete(tier)

    db.commit()
    db.refresh(policy)
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.policy.update",
        target_entity_type="BillingPolicy",
        target_entity_id=str(policy.id),
        after={
            "grace_period_days": policy.grace_period_days,
            "dunning_schedule_days": policy.dunning_schedule_days,
            "tiers": [
                {
                    "id": tier.id,
                    "sequence_order": tier.sequence_order,
                    "trigger_days_after_grace": tier.trigger_days_after_grace,
                    "fee_type": tier.fee_type,
                    "fee_amount": str(tier.fee_amount),
                    "fee_percent": tier.fee_percent,
                }
                for tier in sorted(policy.tiers, key=lambda t: t.sequence_order)
            ],
        },
    )
    return _serialize_policy(policy)


@router.post("/invoices/{invoice_id}/send-reminder")
def send_reminder_notice(
    invoice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN", "SECRETARY")),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "OPEN":
        raise HTTPException(status_code=400, detail="Reminders can only be sent for open invoices")

    applied_invoice_ids = auto_apply_late_fees(db)
    if applied_invoice_ids:
        db.commit()

    owner = db.get(Owner, invoice.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found for invoice")

    policy = get_or_create_billing_policy(db)
    today = date.today()
    days_past_due = max(0, (today - invoice.due_date).days)
    days_after_grace = max(0, days_past_due - policy.grace_period_days)

    sorted_schedule: Sequence[int] = sorted(policy.dunning_schedule_days or [])
    next_notice = next((day for day in sorted_schedule if day > days_after_grace), None)

    pdf_path = generate_reminder_notice_pdf(
        invoice=invoice,
        owner=owner,
        actor=actor,
        days_past_due=days_past_due,
        grace_period_days=policy.grace_period_days,
        next_notice_in_days=next_notice,
    )

    invoice.last_reminder_sent_at = datetime.utcnow()
    db.add(invoice)
    db.commit()

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.invoice.reminder",
        target_entity_type="Invoice",
        target_entity_id=str(invoice.id),
        after={
            "reminder_sent_at": invoice.last_reminder_sent_at.isoformat(),
            "days_past_due": days_past_due,
            "next_notice_in_days": next_notice,
        },
    )

    filename = f"invoice_{invoice.id}_reminder.pdf"
    return FileResponse(path=pdf_path, media_type="application/pdf", filename=filename)
