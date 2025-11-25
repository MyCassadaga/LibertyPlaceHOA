from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import decode_token, get_current_user, require_roles
from ..models.models import Notification, User
from ..schemas.schemas import NotificationBroadcast, NotificationRead
from ..services.notifications import (
    create_notification,
    notification_center,
    notification_websocket_handler,
)

router = APIRouter()


@router.get("/", response_model=List[NotificationRead])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    include_read: bool = Query(True),
    levels: Optional[List[str]] = Query(None, description="Filter by notification level."),
    categories: Optional[List[str]] = Query(None, description="Filter by category."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Notification]:
    query = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if not include_read:
        query = query.filter(Notification.read_at.is_(None))
    if levels:
        normalized_levels = sorted({level.lower() for level in levels if level})
        if normalized_levels:
            query = query.filter(func.lower(Notification.level).in_(normalized_levels))
    if categories:
        normalized_categories = sorted({category.lower() for category in categories if category})
        if normalized_categories:
            query = query.filter(func.lower(Notification.category).in_(normalized_categories))
    notifications = query.limit(limit).all()
    return notifications


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.add(notification)
        db.commit()
        db.refresh(notification)
        notification_center.dispatch_read(current_user.id, notification.id, notification.read_at)
    return notification


@router.post("/read-all", response_model=dict)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    unread_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .all()
    )
    if not unread_notifications:
        return {"updated": 0}
    timestamp = datetime.now(timezone.utc)
    for notification in unread_notifications:
        notification.read_at = timestamp
        db.add(notification)
    db.commit()
    notification_center.dispatch_bulk_read(current_user.id, [item.id for item in unread_notifications])
    return {"updated": len(unread_notifications)}


@router.post("/broadcast", response_model=dict)
def broadcast_notification(
    payload: NotificationBroadcast,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("SYSADMIN")),
) -> dict:
    notifications = create_notification(
        db,
        title=payload.title,
        message=payload.message,
        level=payload.level or "info",
        category=payload.category,
        link_url=payload.link_url,
        user_ids=payload.user_ids,
        role_names=payload.roles,
    )
    db.commit()
    return {"created": len(notifications)}


@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> None:
    if not token:
        await websocket.close(code=4401)
        return
    try:
        decoded = decode_token(token)
    except JWTError:
        await websocket.close(code=4401)
        return

    if decoded.get("type") not in (None, "access"):
        await websocket.close(code=4401)
        return

    user_sub = decoded.get("sub")
    if not user_sub:
        await websocket.close(code=4401)
        return

    user_id = int(user_sub)
    user = db.get(User, user_id)
    if not user or not user.is_active:
        await websocket.close(code=4403)
        return

    await notification_websocket_handler(user_id, websocket, db)
