from enum import Enum
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Announcement, EmailBroadcast, Owner, User
from ..schemas.schemas import (
    AnnouncementCreate,
    AnnouncementRead,
    EmailBroadcastCreate,
    EmailBroadcastRead,
    EmailBroadcastSegmentPreview,
)
from ..services import email
from ..services.billing import calculate_owner_balance
from ..services.audit import audit_log
from ..utils.pdf_utils import generate_announcement_packet

router = APIRouter()


def _queue_email(background: BackgroundTasks, subject: str, body: str, recipients: List[str]) -> None:
    background.add_task(email.send_announcement, subject, body, recipients)


class BroadcastSegment(str, Enum):
    ALL_OWNERS = "ALL_OWNERS"
    DELINQUENT_OWNERS = "DELINQUENT_OWNERS"
    RENTAL_OWNERS = "RENTAL_OWNERS"


SEGMENT_DETAILS: Dict[BroadcastSegment, Dict[str, str]] = {
    BroadcastSegment.ALL_OWNERS: {
        "label": "All Owners",
        "description": "Every owner record with at least one email on file.",
    },
    BroadcastSegment.DELINQUENT_OWNERS: {
        "label": "Delinquent Owners",
        "description": "Owners with an outstanding balance greater than zero.",
    },
    BroadcastSegment.RENTAL_OWNERS: {
        "label": "Rental Owners",
        "description": "Owners flagged as rental properties.",
    },
}


def _owner_contacts(owner: Owner) -> List[Dict[str, Optional[str]]]:
    contacts: List[Dict[str, Optional[str]]] = []
    if owner.primary_email:
        contacts.append(
            {
                "owner_id": owner.id,
                "owner_name": owner.primary_name,
                "lot": owner.lot,
                "email": owner.primary_email,
                "contact_type": "primary",
            }
        )
    if owner.secondary_email:
        contacts.append(
            {
                "owner_id": owner.id,
                "owner_name": owner.primary_name,
                "lot": owner.lot,
                "email": owner.secondary_email,
                "contact_type": "secondary",
            }
        )
    return contacts


def _dedupe_and_sort(recipients: List[Dict[str, Optional[str]]]) -> List[Dict[str, Optional[str]]]:
    seen = set()
    unique: List[Dict[str, Optional[str]]] = []
    for recipient in recipients:
        email_value = recipient.get("email")
        if not email_value:
            continue
        email_key = email_value.lower()
        if email_key in seen:
            continue
        seen.add(email_key)
        unique.append(recipient)
    unique.sort(key=lambda item: ((item.get("owner_name") or "") + "|" + (item.get("email") or "")))
    return unique


def _resolve_segment_recipients(db: Session, segment: BroadcastSegment) -> List[Dict[str, Optional[str]]]:
    owners = db.query(Owner).order_by(Owner.primary_name.asc()).all()

    if segment == BroadcastSegment.RENTAL_OWNERS:
        owners = [owner for owner in owners if owner.is_rental]
    elif segment == BroadcastSegment.DELINQUENT_OWNERS:
        filtered: List[Owner] = []
        for owner in owners:
            balance = calculate_owner_balance(db, owner.id)
            if balance > 0:
                filtered.append(owner)
        owners = filtered

    recipients: List[Dict[str, Optional[str]]] = []
    for owner in owners:
        recipients.extend(_owner_contacts(owner))

    return _dedupe_and_sort(recipients)


@router.get("/broadcast-segments", response_model=List[EmailBroadcastSegmentPreview])
def list_broadcast_segments(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[EmailBroadcastSegmentPreview]:
    previews: List[EmailBroadcastSegmentPreview] = []
    for segment in BroadcastSegment:
        recipients = _resolve_segment_recipients(db, segment)
        metadata = SEGMENT_DETAILS.get(segment, {"label": segment.value.title(), "description": ""})
        previews.append(
            EmailBroadcastSegmentPreview(
                key=segment.value,
                label=metadata["label"],
                description=metadata["description"],
                recipient_count=len(recipients),
            )
        )
    return previews


@router.get("/broadcasts", response_model=List[EmailBroadcastRead])
def list_email_broadcasts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[EmailBroadcast]:
    return db.query(EmailBroadcast).order_by(EmailBroadcast.created_at.desc()).all()


@router.post("/broadcasts", response_model=EmailBroadcastRead, status_code=status.HTTP_201_CREATED)
def create_email_broadcast(
    payload: EmailBroadcastCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> EmailBroadcast:
    try:
        segment = BroadcastSegment(payload.segment)
    except ValueError as exc:  # pragma: no cover - defensive, should be prevented by schema Literal
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown recipient segment.") from exc

    recipients = _resolve_segment_recipients(db, segment)
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipients have emails for the selected segment. Update owner records before broadcasting.",
        )

    subject = payload.subject.strip()
    body = payload.body.strip()
    if not subject or not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject and body cannot be empty.")

    broadcast = EmailBroadcast(
        subject=subject,
        body=body,
        segment=segment.value,
        recipient_snapshot=recipients,
        recipient_count=len(recipients),
        created_by_user_id=actor.id,
    )
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="communications.broadcast.create",
        target_entity_type="EmailBroadcast",
        target_entity_id=str(broadcast.id),
        after={
            "subject": broadcast.subject,
            "segment": segment.value,
            "recipient_count": broadcast.recipient_count,
        },
    )
    return broadcast


@router.get("/announcements", response_model=List[AnnouncementRead])
def list_announcements(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[Announcement]:
    return db.query(Announcement).order_by(Announcement.created_at.desc()).all()


@router.post("/announcements", response_model=AnnouncementRead)
def create_announcement(
    payload: AnnouncementCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> Announcement:
    recipient_emails = [owner.primary_email for owner in db.query(Owner).all() if owner.primary_email]
    pdf_path = None
    if "print" in [method.lower() for method in payload.delivery_methods]:
        pdf_path = generate_announcement_packet(payload.subject, payload.body)

    announcement = Announcement(
        subject=payload.subject,
        body=payload.body,
        created_by_user_id=actor.id,
        delivery_methods=payload.delivery_methods,
        pdf_path=pdf_path,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    if "email" in [method.lower() for method in payload.delivery_methods]:
        _queue_email(background, payload.subject, payload.body, recipient_emails)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="communications.announcement.create",
        target_entity_type="Announcement",
        target_entity_id=str(announcement.id),
        after=payload.dict(),
    )
    return announcement
