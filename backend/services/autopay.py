from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from ..models.models import AutopayEnrollment, Invoice, Owner, Payment
from ..services.audit import audit_log
from ..services.billing import record_payment

AUTOPAY_DELAY_DAYS = 30


def _eligible_enrollments(session: Session) -> Iterable[AutopayEnrollment]:
    return (
        session.query(AutopayEnrollment)
        .join(Owner, Owner.id == AutopayEnrollment.owner_id)
        .filter(Owner.is_archived.is_(False))
        .filter(AutopayEnrollment.cancelled_at.is_(None))
        .filter(AutopayEnrollment.paused_at.is_(None))
        .filter(AutopayEnrollment.status != "CANCELLED")
        .all()
    )


def _invoice_is_due(invoice: Invoice, as_of: date) -> bool:
    if not invoice.created_at:
        return False
    posted_on = invoice.created_at.date()
    return (as_of - posted_on).days >= AUTOPAY_DELAY_DAYS


def _resolve_payment_amount(invoice: Invoice, enrollment: AutopayEnrollment) -> Decimal:
    amount = Decimal(str(invoice.amount))
    if enrollment.amount_type == "FIXED":
        fixed_amount = Decimal(str(enrollment.fixed_amount or 0))
        amount = min(amount, fixed_amount)
    return amount


def run_autopay_charges(session: Session, as_of: Optional[date] = None) -> List[int]:
    as_of_date = as_of or date.today()
    paid_invoice_ids: List[int] = []
    run_timestamp = datetime.combine(as_of_date, datetime.min.time(), tzinfo=timezone.utc)

    enrollments = {enrollment.owner_id: enrollment for enrollment in _eligible_enrollments(session)}
    if not enrollments:
        return paid_invoice_ids

    invoices = (
        session.query(Invoice)
        .join(Owner, Owner.id == Invoice.owner_id)
        .filter(Invoice.status == "OPEN")
        .filter(Owner.is_archived.is_(False))
        .order_by(Invoice.created_at.asc())
        .all()
    )

    for invoice in invoices:
        if invoice.owner_id not in enrollments:
            continue
        if not _invoice_is_due(invoice, as_of_date):
            continue
        existing_payment = (
            session.query(Payment)
            .filter(Payment.invoice_id == invoice.id, Payment.method == "autopay")
            .first()
        )
        if existing_payment:
            continue
        enrollment = enrollments[invoice.owner_id]
        amount = _resolve_payment_amount(invoice, enrollment)
        if amount <= 0:
            continue

        payment = Payment(
            owner_id=invoice.owner_id,
            invoice_id=invoice.id,
            amount=amount,
            method="autopay",
            reference=f"AUTOPAY-{invoice.id}-{as_of_date.isoformat()}",
            date_received=run_timestamp,
            notes="Scheduled autopay",
        )
        session.add(payment)
        session.flush()
        record_payment(session, payment)
        if amount >= Decimal(str(invoice.amount)):
            invoice.status = "PAID"
            session.add(invoice)
        enrollment.last_run_at = run_timestamp
        session.add(enrollment)
        paid_invoice_ids.append(invoice.id)
        audit_log(
            db_session=session,
            actor_user_id=enrollment.user_id,
            action="payments.autopay.charge",
            target_entity_type="Payment",
            target_entity_id=str(payment.id),
            after={
                "invoice_id": invoice.id,
                "owner_id": invoice.owner_id,
                "amount": str(amount),
                "scheduled_for": run_timestamp.isoformat(),
            },
        )

    if paid_invoice_ids:
        session.commit()
    return paid_invoice_ids
