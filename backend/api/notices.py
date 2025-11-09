from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import NoticeType, Owner, User
from ..schemas.schemas import NoticeCreateRequest, NoticeRead
from ..services import notices as notice_service

router = APIRouter(prefix="/notices", tags=["notices"])


@router.post("/", response_model=NoticeRead)
def create_notice_endpoint(
    payload: NoticeCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
):
    owner = db.get(Owner, payload.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    notice_type = (
        db.query(NoticeType)
        .filter(NoticeType.code == payload.notice_type_code.upper())
        .first()
    )
    if not notice_type:
        raise HTTPException(status_code=404, detail="Notice type not found")

    notice = notice_service.create_notice(
        db,
        owner=owner,
        notice_type=notice_type,
        subject=payload.subject,
        body_html=payload.body_html,
        created_by=user,
    )
    db.commit()
    db.refresh(notice)
    return NoticeRead.from_orm(notice)
