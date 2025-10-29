from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from ..models.models import Contract, Reminder

RENEWAL_REMINDER_TYPE = "renewal_warning"
CONTRACT_ENTITY_TYPE = "Contract"


def generate_contract_renewal_reminders(session: Session, window_days: int = 30) -> List[Reminder]:
    """Create renewal reminders for contracts approaching their termination notice deadline."""
    today = date.today()
    start_of_today = datetime.combine(today, datetime.min.time())
    cutoff = today + timedelta(days=window_days)

    contracts = (
        session.query(Contract)
        .filter(
            Contract.termination_notice_deadline.isnot(None),
            Contract.termination_notice_deadline >= today,
            Contract.termination_notice_deadline <= cutoff,
        )
        .order_by(Contract.termination_notice_deadline.asc())
        .all()
    )

    created: List[Reminder] = []
    for contract in contracts:
        existing = (
            session.query(Reminder)
            .filter(
                Reminder.reminder_type == RENEWAL_REMINDER_TYPE,
                Reminder.entity_type == CONTRACT_ENTITY_TYPE,
                Reminder.entity_id == contract.id,
                Reminder.created_at >= start_of_today,
            )
            .first()
        )
        if existing:
            continue

        reminder = Reminder(
            reminder_type=RENEWAL_REMINDER_TYPE,
            title=f"Contract renewal notice – {contract.vendor_name}",
            description=(
                f"Termination notice deadline on {contract.termination_notice_deadline:%b %d, %Y}. "
                "Review renewal terms or notify the vendor."
            ),
            entity_type=CONTRACT_ENTITY_TYPE,
            entity_id=contract.id,
            due_date=contract.termination_notice_deadline,
            context={
                "contract_id": contract.id,
                "vendor_name": contract.vendor_name,
                "service_type": contract.service_type,
                "termination_notice_deadline": contract.termination_notice_deadline.isoformat(),
            },
        )
        session.add(reminder)
        session.flush()
        created.append(reminder)
    return created
