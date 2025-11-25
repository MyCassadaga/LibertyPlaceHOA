from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Meeting, User
from ..schemas.schemas import MeetingCreate, MeetingRead, MeetingUpdate
from ..services.storage import storage_service

router = APIRouter(prefix="/meetings", tags=["meetings"])

MANAGER_ROLES = ("BOARD", "SYSADMIN", "SECRETARY", "TREASURER")


def _serialize_meeting(meeting: Meeting) -> MeetingRead:
    minutes_available = bool(meeting.minutes_file_path)
    download_url = f"/meetings/{meeting.id}/minutes" if minutes_available else None
    return MeetingRead(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        location=meeting.location,
        zoom_link=meeting.zoom_link,
        minutes_available=minutes_available,
        minutes_download_url=download_url,
        created_by_user_id=meeting.created_by_user_id,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


@router.get("/", response_model=list[MeetingRead])
def list_meetings(
    include_past: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MeetingRead]:
    query = db.query(Meeting).order_by(Meeting.start_time.asc())
    if not include_past:
        query = query.filter(Meeting.start_time >= datetime.now(timezone.utc))
    meetings = query.all()
    return [_serialize_meeting(meeting) for meeting in meetings]


@router.post("/", response_model=MeetingRead)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGER_ROLES)),
) -> MeetingRead:
    meeting = Meeting(
        title=payload.title.strip(),
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        zoom_link=payload.zoom_link,
        created_by_user_id=user.id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize_meeting(meeting)


@router.patch("/{meeting_id}", response_model=MeetingRead)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> MeetingRead:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(meeting, key, value)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize_meeting(meeting)


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> Response:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.minutes_file_path:
        storage_service.delete_file(meeting.minutes_file_path)
    db.delete(meeting)
    db.commit()
    return Response(status_code=204)


@router.post("/{meeting_id}/minutes", response_model=MeetingRead)
async def upload_minutes(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> MeetingRead:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Minutes file is empty")
    relative_path = f"meetings/{meeting_id}/minutes_{datetime.now(timezone.utc).timestamp()}_{file.filename or 'minutes.txt'}"
    stored = storage_service.save_file(relative_path, content, content_type=file.content_type)
    if meeting.minutes_file_path:
        storage_service.delete_file(meeting.minutes_file_path)
    meeting.minutes_file_path = stored.relative_path
    meeting.minutes_content_type = file.content_type
    meeting.minutes_file_size = len(content)
    meeting.minutes_uploaded_at = datetime.now(timezone.utc)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize_meeting(meeting)


@router.get("/{meeting_id}/minutes")
def download_minutes(
    meeting_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or not meeting.minutes_file_path:
        raise HTTPException(status_code=404, detail="Minutes not available")
    stored = storage_service.retrieve_file(meeting.minutes_file_path)
    extension = ""
    if "." in meeting.minutes_file_path:
        extension = meeting.minutes_file_path.rsplit(".", 1)[-1]
    filename = f"meeting-{meeting_id}-minutes"
    if extension:
        filename = f"{filename}.{extension}"
    return Response(
        content=stored.content,
        media_type=stored.content_type or meeting.minutes_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
