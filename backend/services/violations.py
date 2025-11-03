from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from ..models.models import Appeal, Owner, User, Violation, ViolationNotice
from ..services import email
from ..services.audit import audit_log
from ..utils.pdf_utils import generate_violation_notice_pdf

VIOLATION_STATES = [
    "NEW",
    "UNDER_REVIEW",
    "WARNING_SENT",
    "HEARING",
    "FINE_ACTIVE",
    "RESOLVED",
    "ARCHIVED",
]

ALLOWED_TRANSITIONS: Dict[str, set[str]] = {
    "NEW": {"UNDER_REVIEW", "ARCHIVED"},
    "UNDER_REVIEW": {"WARNING_SENT", "ARCHIVED"},
    "WARNING_SENT": {"HEARING", "RESOLVED"},
    "HEARING": {"FINE_ACTIVE", "RESOLVED"},
    "FINE_ACTIVE": {"RESOLVED"},
    "RESOLVED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

NOTICE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "WARNING_SENT": {
        "subject": "Covenant Warning for {address}",
        "body": (
            "Dear {owner_name},\n\n"
            "The association has reviewed the reported covenant concern ({category}) and issued a warning.\n"
            "Details:\n{description}\n\n"
            "Please resolve the issue by {due_date} to avoid escalation.\n\n"
            "Thank you,\nLiberty Place HOA Board"
        ),
    },
    "HEARING": {
        "subject": "Hearing Scheduled for Violation #{violation_id}",
        "body": (
            "Dear {owner_name},\n\n"
            "A hearing has been scheduled on {hearing_date} regarding the following:\n{description}\n\n"
            "Please attend the meeting or contact the board if you require accommodations.\n\n"
            "Regards,\nLiberty Place HOA Board"
        ),
    },
    "FINE_ACTIVE": {
        "subject": "Fine Issued for Violation #{violation_id}",
        "body": (
            "Dear {owner_name},\n\n"
            "A fine of ${fine_amount} has been assessed for the covenant violation ({category}).\n"
            "Please remit payment or appeal by {due_date}.\n\n"
            "Regards,\nLiberty Place HOA Board"
        ),
    },
}

NOTICE_DIRECTORY = Path("uploads/violations")
NOTICE_DIRECTORY.mkdir(parents=True, exist_ok=True)


def _format_template(template: str, violation: Violation, owner: Owner, fine_amount: Optional[Decimal]) -> str:
    return template.format(
        owner_name=owner.primary_name,
        address=owner.property_address or "Pending address",
        violation_id=violation.id,
        category=violation.category,
        description=violation.description or "",
        due_date=violation.due_date.isoformat() if violation.due_date else "N/A",
        hearing_date=violation.hearing_date.isoformat() if violation.hearing_date else "TBD",
        fine_amount=f"{fine_amount:.2f}" if fine_amount is not None else "0.00",
    )


def _create_notice(
    session: Session,
    violation: Violation,
    owner: Owner,
    actor: User,
    template_key: str,
) -> ViolationNotice:
    template = NOTICE_TEMPLATES[template_key]
    subject = _format_template(template["subject"], violation, owner, violation.fine_amount)
    body = _format_template(template["body"], violation, owner, violation.fine_amount)
    pdf_path = Path(generate_violation_notice_pdf(template_key, violation, owner, subject, body))
    target_path = NOTICE_DIRECTORY / pdf_path.name
    try:
        target_path.write_text(pdf_path.read_text())
    except FileNotFoundError:
        target_path.write_text(body)
    relative_pdf_path = str(target_path)

    notice = ViolationNotice(
        violation_id=violation.id,
        sent_by_user_id=actor.id,
        notice_type="EMAIL",
        template_key=template_key,
        subject=subject,
        body=body,
        pdf_path=relative_pdf_path,
    )
    session.add(notice)
    session.flush()

    recipients = [owner.primary_email] if owner.primary_email else []
    if recipients:
        email.send_announcement(subject, body, recipients)

    return notice


def transition_violation(
    session: Session,
    violation: Violation,
    actor: User,
    target_status: str,
    note: Optional[str] = None,
    hearing_date: Optional[date] = None,
    fine_amount: Optional[Decimal] = None,
) -> Violation:
    current_status = violation.status
    if target_status not in VIOLATION_STATES:
        raise ValueError("Invalid violation status.")
    if target_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError(f"Cannot transition from {current_status} to {target_status}.")

    owner = session.get(Owner, violation.owner_id)
    if owner is None:
        raise ValueError("Associated owner not found for violation.")

    if hearing_date:
        violation.hearing_date = hearing_date
    if fine_amount is not None:
        violation.fine_amount = fine_amount
    violation.status = target_status
    violation.updated_at = datetime.utcnow()
    session.add(violation)
    session.flush()

    if target_status in NOTICE_TEMPLATES:
        _create_notice(session, violation, owner, actor, target_status)

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="violations.transition",
        target_entity_type="Violation",
        target_entity_id=str(violation.id),
        before={"status": current_status},
        after={
            "status": target_status,
            "note": note,
            "hearing_date": violation.hearing_date.isoformat() if violation.hearing_date else None,
            "fine_amount": str(violation.fine_amount) if violation.fine_amount is not None else None,
        },
    )
    return violation


def create_appeal(session: Session, violation: Violation, owner: Owner, reason: str) -> Appeal:
    appeal = Appeal(
        violation_id=violation.id,
        submitted_by_owner_id=owner.id,
        reason=reason,
    )
    session.add(appeal)
    session.flush()
    return appeal
