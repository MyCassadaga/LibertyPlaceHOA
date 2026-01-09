import logging
from enum import Enum
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Announcement, CommunicationMessage, EmailBroadcast, Owner, User
from ..schemas.schemas import (
    AnnouncementCreate,
    AnnouncementRead,
    CommunicationMessageCreate,
    CommunicationMessageRead,
    EmailBroadcastCreate,
    EmailBroadcastRead,
    EmailBroadcastSegmentPreview,
)
from ..services import email
from ..services.billing import calculate_owner_balance
from ..services.audit import audit_log
from ..utils.pdf_utils import generate_announcement_packet

router = APIRouter()
logger = logging.getLogger(__name__)


def _queue_email(background: BackgroundTasks, subject: str, body: str, recipients: List[str]) -> None:
    def _send() -> None:
        try:
            email.send_announcement(subject, body, recipients)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Announcement email dispatch failed.")
            raise

    logger.info("Queueing announcement email for %d recipients.", len(recipients))
    background.add_task(_send)


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
                "property_address": owner.property_address,
                "email": owner.primary_email,
                "contact_type": "primary",
            }
        )
    if owner.secondary_email:
        contacts.append(
            {
                "owner_id": owner.id,
                "owner_name": owner.primary_name,
                "property_address": owner.property_address,
                "email": owner.secondary_email,
                "contact_type": "secondary",
            }
        )
    return contacts


def _announcement_recipients(owners: List[Owner], delivery_methods: List[str]) -> List[Dict[str, Optional[str]]]:
    recipients: List[Dict[str, Optional[str]]] = []
    delivery_set = {method.lower() for method in delivery_methods}
    if "email" in delivery_set:
        for owner in owners:
            recipients.extend(_owner_contacts(owner))
    if "print" in delivery_set:
        for owner in owners:
            recipients.append(
                {
                    "owner_id": owner.id,
                    "owner_name": owner.primary_name,
                    "property_address": owner.property_address,
                    "mailing_address": owner.mailing_address or owner.property_address,
                    "email": None,
                    "contact_type": "mailing",
                }
            )
    return recipients


def _sender_snapshot(actor: User) -> Dict[str, Optional[str]]:
    return {
        "user_id": actor.id,
        "full_name": actor.full_name,
        "email": actor.email,
    }


def _dedupe_and_sort(recipients: List[Dict[str, Optional[str]]]) -> List[Dict[str, Optional[str]]]:
    seen = set()
    unique: List[Dict[str, Optional[str]]] = []
    for recipient in recipients:
        email_value = recipient.get("email")
        address_value = recipient.get("mailing_address")
        if email_value:
            dedupe_key = email_value.lower()
        elif address_value:
            dedupe_key = address_value.lower()
        else:
            continue
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique.append(recipient)
    unique.sort(
        key=lambda item: (
            (item.get("owner_name") or "")
            + "|"
            + (item.get("email") or "")
            + "|"
            + (item.get("mailing_address") or "")
        )
    )
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


@router.get("/broadcasts", response_model=List[EmailBroadcastRead], response_model_by_alias=False)
def list_email_broadcasts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[EmailBroadcastRead]:
    broadcasts = db.query(EmailBroadcast).order_by(EmailBroadcast.created_at.desc()).all()
    return [EmailBroadcastRead.from_orm(broadcast) for broadcast in broadcasts]


@router.post(
    "/broadcasts",
    response_model=EmailBroadcastRead,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
def create_email_broadcast(
    payload: EmailBroadcastCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> EmailBroadcastRead:
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
        delivery_methods=["email"],
        sender_snapshot=_sender_snapshot(actor),
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
    return EmailBroadcastRead.from_orm(broadcast)


@router.get("/messages", response_model=List[CommunicationMessageRead], response_model_by_alias=False)
def list_communication_messages(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[CommunicationMessageRead]:
    messages = db.query(CommunicationMessage).order_by(CommunicationMessage.created_at.desc()).all()
    return [CommunicationMessageRead.from_orm(message) for message in messages]


@router.post(
    "/messages",
    response_model=CommunicationMessageRead,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
def create_communication_message(
    payload: CommunicationMessageCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> CommunicationMessageRead:
    subject = payload.subject.strip()
    body = payload.body.strip()
    if not subject or not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject and body cannot be empty.")

    recipient_snapshot: List[Dict[str, Optional[str]]] = []
    recipient_count = 0
    pdf_path = None
    segment_value = None
    delivery_methods: List[str] = []

    if payload.message_type == "BROADCAST":
        try:
            segment = BroadcastSegment(payload.segment)
        except ValueError as exc:  # pragma: no cover - defensive, should be prevented by schema Literal
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown recipient segment."
            ) from exc

        recipient_snapshot = _resolve_segment_recipients(db, segment)
        if not recipient_snapshot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No recipients have emails for the selected segment. Update owner records before broadcasting.",
            )
        segment_value = segment.value
        recipient_count = len(recipient_snapshot)
        delivery_methods = ["email"]
    else:
        delivery_methods = [method.lower() for method in (payload.delivery_methods or ["email"])]
        if not delivery_methods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one delivery method."
            )
        owners = db.query(Owner).order_by(Owner.primary_name.asc()).all()
        recipient_snapshot = _dedupe_and_sort(
            [
                recipient
                for recipient in _announcement_recipients(owners, delivery_methods)
                if recipient.get("contact_type") != "secondary"
            ]
        )
        recipient_emails = [recipient["email"] for recipient in recipient_snapshot if recipient.get("email")]
        recipient_count = len(recipient_snapshot)
        if "print" in delivery_methods:
            pdf_path = generate_announcement_packet(subject, body)
        if "email" in delivery_methods:
            _queue_email(background, subject, body, recipient_emails)

    message = CommunicationMessage(
        message_type=payload.message_type,
        subject=subject,
        body=body,
        segment=segment_value,
        delivery_methods=delivery_methods,
        recipient_snapshot=recipient_snapshot,
        recipient_count=recipient_count,
        pdf_path=pdf_path,
        created_by_user_id=actor.id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="communications.message.create",
        target_entity_type="CommunicationMessage",
        target_entity_id=str(message.id),
        after={
            "message_type": message.message_type,
            "subject": message.subject,
            "segment": message.segment,
            "delivery_methods": message.delivery_methods,
            "recipient_count": message.recipient_count,
        },
    )
    return CommunicationMessageRead.from_orm(message)


@router.get("/announcements", response_model=List[AnnouncementRead], response_model_by_alias=False)
def list_announcements(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[Announcement]:
    return db.query(Announcement).order_by(Announcement.created_at.desc()).all()


@router.post("/announcements", response_model=AnnouncementRead, response_model_by_alias=False)
def create_announcement(
    payload: AnnouncementCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> Announcement:
    owners = db.query(Owner).all()
    delivery_methods = [method.lower() for method in payload.delivery_methods]
    recipients = _dedupe_and_sort(_announcement_recipients(owners, delivery_methods))
    recipient_emails = [recipient["email"] for recipient in recipients if recipient.get("email")]
    pdf_path = None
    if "print" in delivery_methods:
        pdf_path = generate_announcement_packet(payload.subject, payload.body)

    announcement = Announcement(
        subject=payload.subject,
        body=payload.body,
        created_by_user_id=actor.id,
        delivery_methods=payload.delivery_methods,
        recipient_snapshot=recipients,
        recipient_count=len(recipients),
        sender_snapshot=_sender_snapshot(actor),
        pdf_path=pdf_path,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    if "email" in delivery_methods:
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
