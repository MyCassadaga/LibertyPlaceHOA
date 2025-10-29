from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from ..models.models import (
    BillingPolicy,
    Invoice,
    InvoiceLateFee,
    LateFeeTier,
    LedgerEntry,
    Owner,
    Payment,
)

DEFAULT_POLICY_NAME = "default"
DEFAULT_GRACE_PERIOD_DAYS = 5
DEFAULT_DUNNING_SCHEDULE = [5, 15, 30]


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


def get_or_create_billing_policy(session: Session) -> BillingPolicy:
    policy = session.query(BillingPolicy).filter(BillingPolicy.name == DEFAULT_POLICY_NAME).first()
    if policy:
        return policy

    policy = BillingPolicy(
        name=DEFAULT_POLICY_NAME,
        grace_period_days=DEFAULT_GRACE_PERIOD_DAYS,
        dunning_schedule_days=DEFAULT_DUNNING_SCHEDULE,
    )
    session.add(policy)
    session.flush()
    return policy


def _calculate_tier_charge(invoice: Invoice, tier: LateFeeTier) -> Decimal:
    base = _ensure_decimal(invoice.original_amount or invoice.amount)
    if tier.fee_type == "percent":
        percentage = Decimal(str(tier.fee_percent)) / Decimal("100")
        return (base * percentage).quantize(Decimal("0.01"))
    return _ensure_decimal(tier.fee_amount)


def record_invoice(session: Session, invoice: Invoice) -> LedgerEntry:
    owner = session.query(Owner).filter(Owner.id == invoice.owner_id).one()
    if not invoice.original_amount:
        invoice.original_amount = invoice.amount
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


def apply_manual_late_fee(session: Session, invoice: Invoice, fee_amount: Decimal, description: Optional[str] = None) -> Invoice:
    fee_amount = _ensure_decimal(fee_amount)
    if fee_amount <= 0:
        return invoice

    invoice.amount = _ensure_decimal(invoice.amount) + fee_amount
    invoice.late_fee_total = _ensure_decimal(invoice.late_fee_total) + fee_amount
    invoice.late_fee_applied = True
    invoice.last_late_fee_applied_at = datetime.utcnow()
    session.add(invoice)
    session.flush()

    owner = session.query(Owner).filter(Owner.id == invoice.owner_id).one()
    _create_ledger_entry(
        session=session,
        owner=owner,
        entry_type="adjustment",
        amount=fee_amount,
        description=description or f"Manual late fee applied to Invoice #{invoice.id}",
    )
    return invoice


def apply_late_fee(session: Session, invoice: Invoice, tier: LateFeeTier) -> bool:
    if any(fee.tier_id == tier.id for fee in invoice.late_fees):
        return False

    fee_amount = _calculate_tier_charge(invoice, tier)
    if fee_amount <= 0:
        return False

    invoice.amount = _ensure_decimal(invoice.amount) + fee_amount
    invoice.late_fee_total = _ensure_decimal(invoice.late_fee_total) + fee_amount
    invoice.late_fee_applied = True
    invoice.last_late_fee_applied_at = datetime.utcnow()
    session.add(invoice)
    session.flush()  # ensure invoice id for ledger references

    fee_record = InvoiceLateFee(invoice_id=invoice.id, tier_id=tier.id, fee_amount=fee_amount)
    session.add(fee_record)
    session.flush()

    owner = session.query(Owner).filter(Owner.id == invoice.owner_id).one()
    _create_ledger_entry(
        session=session,
        owner=owner,
        entry_type="adjustment",
        amount=fee_amount,
        description=tier.description or f"Late fee tier {tier.sequence_order} applied to Invoice #{invoice.id}",
    )
    return True


def auto_apply_late_fees(session: Session) -> List[int]:
    policy = get_or_create_billing_policy(session)
    tiers: Sequence[LateFeeTier] = (
        session.query(LateFeeTier)
        .filter(LateFeeTier.policy_id == policy.id)
        .order_by(LateFeeTier.sequence_order.asc())
        .all()
    )
    if not tiers:
        return []

    today = date.today()
    applied_invoice_ids: List[int] = []

    open_invoices: Sequence[Invoice] = (
        session.query(Invoice)
        .filter(Invoice.status == "OPEN")
        .order_by(Invoice.due_date.asc())
        .all()
    )

    for invoice in open_invoices:
        days_past_due = (today - invoice.due_date).days
        if days_past_due <= policy.grace_period_days:
            continue
        days_after_grace = days_past_due - policy.grace_period_days

        for tier in tiers:
            if days_after_grace < tier.trigger_days_after_grace:
                break
            applied = apply_late_fee(session, invoice, tier)
            if applied:
                applied_invoice_ids.append(invoice.id)
    return applied_invoice_ids
