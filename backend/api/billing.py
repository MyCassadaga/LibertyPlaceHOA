from datetime import datetime, date, timezone
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import Dict, List, Sequence

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..config import settings
from ..models.models import BillingPolicy, Invoice, LateFeeTier, LedgerEntry, Owner, OwnerUserLink, Payment, User
from ..schemas.schemas import (
    BillingPolicyRead,
    BillingPolicyUpdate,
    BillingSummaryRead,
    ForwardAttorneyRequest,
    ForwardAttorneyResponse,
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    LedgerEntryRead,
    LateFeePayload,
    OverdueAccountRead,
    OverdueContactRequest,
    OverdueContactResponse,
    OverdueInvoiceRead,
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
from ..services.notifications import create_notification
from ..utils.pdf_utils import generate_attorney_notice_pdf, generate_reminder_notice_pdf

router = APIRouter()
OVERDUE_LIST_ROLES = ("BOARD", "TREASURER", "SYSADMIN", "AUDITOR")


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


def _group_overdue_invoices(db: Session) -> Dict[int, List[Invoice]]:
    today = date.today()
    overdue_invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.owner))
        .join(Owner, Owner.id == Invoice.owner_id)
        .filter(Owner.is_archived.is_(False))
        .filter(Invoice.status == "OPEN")
        .filter(Invoice.due_date < today)
        .order_by(Invoice.owner_id.asc(), Invoice.due_date.asc())
        .all()
    )
    grouped: Dict[int, List[Invoice]] = {}
    for invoice in overdue_invoices:
        grouped.setdefault(invoice.owner_id, []).append(invoice)
    return grouped


def _months_overdue(days_overdue: int) -> int:
    if days_overdue <= 0:
        return 0
    return ceil(days_overdue / 30)


def _public_notice_url(pdf_path: str) -> str:
    try:
        resolved = Path(pdf_path).resolve()
        uploads_root = settings.uploads_root_path
        relative = resolved.relative_to(uploads_root).as_posix()
        public_prefix = settings.uploads_public_prefix.strip("/")
        public_path = f"{public_prefix}/{relative}".lstrip("/")
        return f"/{public_path}"
    except Exception:
        normalized = pdf_path.replace("\\", "/")
        return normalized if normalized.startswith("/") else f"/{normalized}"


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

    invoice.last_reminder_sent_at = datetime.now(timezone.utc)
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


def _default_contact_message(owner: Owner, invoices: Sequence[Invoice]) -> str:
    total_due = sum((_as_decimal(invoice.amount) for invoice in invoices), Decimal("0"))
    today = date.today()
    longest_days = max(((today - invoice.due_date).days for invoice in invoices), default=0)
    months = _months_overdue(longest_days)
    address = owner.property_address or owner.mailing_address or "your property"
    balance = total_due.quantize(Decimal("0.01"))
    months_label = f"{months} month(s)" if months else "less than a month"
    return (
        f"Hello {owner.primary_name}, your HOA account for {address} is {months_label} past due "
        f"with a balance of ${balance}. Please sign in to the portal or contact the board "
        "within 10 days to avoid legal escalation."
    )


def _serialize_overdue_invoice(invoice: Invoice, today: date) -> OverdueInvoiceRead:
    days_overdue = max(0, (today - invoice.due_date).days)
    months_overdue = _months_overdue(days_overdue)
    reminders_sent = 1 if invoice.last_reminder_sent_at else 0
    return OverdueInvoiceRead(
        id=invoice.id,
        amount=_as_decimal(invoice.amount),
        due_date=invoice.due_date,
        status=invoice.status,
        days_overdue=days_overdue,
        months_overdue=months_overdue,
        reminders_sent=reminders_sent,
    )


@router.get("/overdue", response_model=List[OverdueAccountRead])
def list_overdue_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OVERDUE_LIST_ROLES)),
) -> List[OverdueAccountRead]:
    grouped = _group_overdue_invoices(db)
    today = date.today()
    overdue_accounts: List[OverdueAccountRead] = []
    for owner_id, invoices in grouped.items():
        owner = invoices[0].owner
        serialized_invoices = [_serialize_overdue_invoice(invoice, today) for invoice in invoices]
        max_months = max((item.months_overdue for item in serialized_invoices), default=0)
        total_due = sum((_as_decimal(invoice.amount) for invoice in invoices), Decimal("0"))
        last_reminder = max(
            (invoice.last_reminder_sent_at for invoice in invoices if invoice.last_reminder_sent_at),
            default=None,
        )
        overdue_accounts.append(
            OverdueAccountRead(
                owner_id=owner_id,
                owner_name=owner.primary_name,
                property_address=owner.property_address,
                primary_email=owner.primary_email,
                primary_phone=owner.primary_phone,
                total_due=total_due,
                max_months_overdue=max_months,
                last_reminder_sent_at=last_reminder,
                invoices=serialized_invoices,
            )
        )
    return overdue_accounts


@router.post(
    "/overdue/{owner_id}/contact",
    response_model=OverdueContactResponse,
)
def contact_overdue_owner(
    owner_id: int,
    payload: OverdueContactRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> OverdueContactResponse:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.user_links).joinedload(OwnerUserLink.user), joinedload(Owner.invoices))
        .filter(Owner.id == owner_id)
        .first()
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    overdue_invoices = [
        invoice
        for invoice in owner.invoices
        if invoice.status == "OPEN" and invoice.due_date < date.today()
    ]
    if not overdue_invoices:
        raise HTTPException(status_code=400, detail="Owner does not have overdue invoices")

    linked_user_ids = [
        link.user_id for link in owner.user_links if link.user and link.user.is_active
    ]
    message = (payload.message or "").strip() or _default_contact_message(owner, overdue_invoices)
    notifications = create_notification(
        db,
        title="Assessment Past Due",
        message=message,
        category="billing",
        user_ids=linked_user_ids if linked_user_ids else None,
    )
    db.commit()

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.overdue.contact",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        after={
            "owner_id": owner.id,
            "invoice_ids": [invoice.id for invoice in overdue_invoices],
            "recipients": linked_user_ids,
            "message": message,
        },
    )
    return OverdueContactResponse(notified_user_ids=[note.user_id for note in notifications])


@router.post("/overdue/{owner_id}/forward-attorney", response_model=ForwardAttorneyResponse)
def forward_overdue_to_attorney(
    owner_id: int,
    payload: ForwardAttorneyRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> ForwardAttorneyResponse:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.invoices))
        .filter(Owner.id == owner_id)
        .first()
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    overdue_invoices = [
        invoice
        for invoice in owner.invoices
        if invoice.status == "OPEN" and invoice.due_date < date.today()
    ]
    if not overdue_invoices:
        raise HTTPException(status_code=400, detail="Owner does not have overdue invoices")

    pdf_path = generate_attorney_notice_pdf(owner, overdue_invoices, payload.notes)
    notice_url = _public_notice_url(pdf_path)
    notification_message = (
        f"{owner.primary_name} has been escalated to legal review "
        f"with ${sum((_as_decimal(inv.amount) for inv in overdue_invoices), Decimal('0'))} outstanding."
    )
    create_notification(
        db,
        title="Attorney Packet Ready",
        message=notification_message,
        category="billing",
        link_url=notice_url,
        role_names=["ATTORNEY"],
    )
    db.commit()

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="billing.overdue.forward_attorney",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        after={
            "owner_id": owner.id,
            "invoice_ids": [invoice.id for invoice in overdue_invoices],
            "notice": notice_url,
            "notes": payload.notes,
        },
    )
    return ForwardAttorneyResponse(notice_url=notice_url)
