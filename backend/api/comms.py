from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Announcement, Owner, User
from ..schemas.schemas import AnnouncementCreate, AnnouncementRead
from ..services import email
from ..services.audit import audit_log
from ..utils.pdf_utils import generate_announcement_packet

router = APIRouter()


def _queue_email(background: BackgroundTasks, subject: str, body: str, recipients: List[str]) -> None:
    background.add_task(email.send_announcement, subject, body, recipients)


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
