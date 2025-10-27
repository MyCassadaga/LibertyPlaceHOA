from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import Invoice, LedgerEntry, Owner, Payment


def _ensure_decimal(amount: Decimal | float | int) -> Decimal:
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


def calculate_owner_balance(session: Session, owner_id: int) -> Decimal:
    balance = Decimal("0")
    entries = (
        session.query(LedgerEntry)
        .filter(LedgerEntry.owner_id == owner_id)
        .order_by(LedgerEntry.timestamp.asc(), LedgerEntry.id.asc())
        .all()
    )
    for entry in entries:
        balance += _ensure_decimal(entry.amount)
    return balance


def _create_ledger_entry(
    session: Session,
    owner: Owner,
    entry_type: str,
    amount: Decimal,
    description: str,
    timestamp: Optional[datetime] = None,
) -> LedgerEntry:
    running_balance = calculate_owner_balance(session, owner.id) + amount
    ledger_entry = LedgerEntry(
        owner_id=owner.id,
        entry_type=entry_type,
        amount=amount,
        balance_after=running_balance,
        description=description,
        timestamp=timestamp or datetime.utcnow(),
    )
    session.add(ledger_entry)
    session.flush()
    return ledger_entry


def record_invoice(session: Session, invoice: Invoice) -> LedgerEntry:
    owner = session.query(Owner).filter(Owner.id == invoice.owner_id).one()
    return _create_ledger_entry(
        session=session,
        owner=owner,
        entry_type="invoice",
        amount=_ensure_decimal(invoice.amount),
        description=f"Invoice #{invoice.id} due {invoice.due_date.isoformat()}",
        timestamp=invoice.created_at,
    )


def record_payment(session: Session, payment: Payment) -> LedgerEntry:
    owner = session.query(Owner).filter(Owner.id == payment.owner_id).one()
    amount = _ensure_decimal(payment.amount) * Decimal("-1")
    description = "Payment received"
    if payment.method:
        description += f" via {payment.method}"
    if payment.reference:
        description += f" ({payment.reference})"
    return _create_ledger_entry(
        session=session,
        owner=owner,
        entry_type="payment",
        amount=amount,
        description=description,
        timestamp=payment.date_received,
    )


def apply_late_fee(session: Session, invoice: Invoice, fee_amount: Decimal) -> Invoice:
    if invoice.late_fee_applied:
        return invoice
    invoice.amount = _ensure_decimal(invoice.amount) + _ensure_decimal(fee_amount)
    invoice.late_fee_applied = True
    session.add(invoice)
    session.flush()
    owner = session.query(Owner).filter(Owner.id == invoice.owner_id).one()
    _create_ledger_entry(
        session=session,
        owner=owner,
        entry_type="adjustment",
        amount=_ensure_decimal(fee_amount),
        description=f"Late fee applied to Invoice #{invoice.id}",
    )
    return invoice
