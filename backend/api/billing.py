from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Invoice, LedgerEntry, Owner, Payment, User
from ..schemas.schemas import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    LedgerEntryRead,
    LateFeePayload,
    PaymentCreate,
    PaymentRead,
    BillingSummaryRead,
)
from ..services.audit import audit_log
from ..services.billing import apply_late_fee, calculate_owner_balance, record_invoice, record_payment

router = APIRouter()


def _as_decimal(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@router.get("/invoices", response_model=List[InvoiceRead])
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> List[Invoice]:
    if user.role and user.role.name == "HOMEOWNER":
        owner = get_owner_for_user(db, user)
        if not owner:
            return []
        return db.query(Invoice).filter(Invoice.owner_id == owner.id).order_by(Invoice.due_date.desc()).all()
    if user.role and user.role.name in {"BOARD", "TREASURER", "SYSADMIN", "AUDITOR"}:
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
    invoice = Invoice(**payload.dict())
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
    before_amount = invoice.amount
    updated = apply_late_fee(db, invoice, _as_decimal(payload.fee_amount))
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

    if user.role and user.role.name == "HOMEOWNER":
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != payload.owner_id:
            raise HTTPException(status_code=403, detail="May only record payments for your own account")
    elif user.role and user.role.name not in {"BOARD", "TREASURER", "SYSADMIN"}:
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

    if user.role and user.role.name == "HOMEOWNER":
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != owner_id:
            raise HTTPException(status_code=403, detail="May only view your own ledger")
    elif user.role and user.role.name not in {"BOARD", "TREASURER", "SYSADMIN", "AUDITOR"}:
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
    owners = db.query(Owner).all()
    total_balance = sum((calculate_owner_balance(db, owner.id) for owner in owners), Decimal("0"))
    open_invoices = db.query(Invoice).filter(Invoice.status == "OPEN").count()
    return BillingSummaryRead(
        total_balance=total_balance,
        open_invoices=open_invoices,
        owner_count=len(owners),
    )
