from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from sqlalchemy.orm import Session

from ..models.models import Notification, Role, User, user_roles
from ..schemas.schemas import NotificationRead

logger = logging.getLogger(__name__)


class NotificationCenter:
    def __init__(self) -> None:
        self._connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def configure_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        logger.debug("NotificationCenter bound to event loop %s", loop)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)
        logger.debug("WebSocket connected for user %s (total=%s)", user_id, len(self._connections[user_id]))

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(user_id)
            if connections and websocket in connections:
                connections.remove(websocket)
            if connections and len(connections) == 0:
                self._connections.pop(user_id, None)
        logger.debug("WebSocket disconnected for user %s", user_id)

    async def _send_to_user(self, user_id: int, payload: dict) -> None:
        async with self._lock:
            connections = list(self._connections.get(user_id, set()))
        for websocket in connections:
            if websocket.application_state != WebSocketState.CONNECTED:
                continue
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                # Connection closed between selection and send
                continue
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to send notification payload to user %s", user_id)

    def _ensure_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        if not self._loop:
            logger.debug("NotificationCenter loop not configured; skipping dispatch.")
            return None
        return self._loop

    def dispatch_created(self, notification: Notification) -> None:
        loop = self._ensure_loop()
        if not loop:
            return
        payload = {
            "type": "notification.created",
            "notification": serialize_notification(notification),
        }
        asyncio.run_coroutine_threadsafe(self._send_to_user(notification.user_id, payload), loop)

    def dispatch_read(self, user_id: int, notification_id: int, read_at: datetime) -> None:
        loop = self._ensure_loop()
        if not loop:
            return
        payload = {
            "type": "notification.read",
            "id": notification_id,
            "read_at": read_at.isoformat(),
        }
        asyncio.run_coroutine_threadsafe(self._send_to_user(user_id, payload), loop)

    def dispatch_bulk_read(self, user_id: int, notification_ids: List[int]) -> None:
        if not notification_ids:
            return
        loop = self._ensure_loop()
        if not loop:
            return
        payload = {
            "type": "notification.bulk_read",
            "ids": notification_ids,
            "read_at": datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run_coroutine_threadsafe(self._send_to_user(user_id, payload), loop)

    async def shutdown(self) -> None:
        async with self._lock:
            connections = list(self._connections.items())
            self._connections.clear()
        for user_id, websockets in connections:
            for websocket in websockets:
                if websocket.application_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.close()
                    except RuntimeError:
                        continue
                    except Exception:  # pragma: no cover - defensive
                        logger.exception("Failed to close WebSocket for user %s", user_id)


notification_center = NotificationCenter()


def serialize_notification(notification: Notification) -> dict:
    return NotificationRead.from_orm(notification).dict()


def _resolve_recipient_ids(
    session: Session,
    user_ids: Optional[Iterable[int]] = None,
    role_names: Optional[Iterable[str]] = None,
) -> List[int]:
    recipients: Set[int] = set()
    if user_ids:
        recipients.update(user_ids)

    if role_names:
        role_names = list(role_names)
        if role_names:
            query = (
                session.query(User.id)
                .join(user_roles, user_roles.c.user_id == User.id)
                .join(Role, Role.id == user_roles.c.role_id)
                .filter(Role.name.in_(role_names), User.is_active.is_(True))
                .distinct()
            )
            for row in query:
                recipients.add(row[0])

    recipients.discard(None)
    return list(recipients)


def create_notification(
    session: Session,
    *,
    title: str,
    message: str,
    level: str = "info",
    category: Optional[str] = None,
    link_url: Optional[str] = None,
    user_ids: Optional[Iterable[int]] = None,
    role_names: Optional[Iterable[str]] = None,
) -> List[Notification]:
    recipient_ids = _resolve_recipient_ids(session, user_ids=user_ids, role_names=role_names)
    if not recipient_ids:
        return []

    notifications: List[Notification] = []
    now = datetime.now(timezone.utc)
    for recipient_id in recipient_ids:
        notification = Notification(
            user_id=recipient_id,
            title=title,
            message=message,
            level=level,
            category=category,
            link_url=link_url,
            created_at=now,
        )
        session.add(notification)
        notifications.append(notification)
    session.flush()

    for notification in notifications:
        notification_center.dispatch_created(notification)

    return notifications


async def notification_websocket_handler(user_id: int, websocket: WebSocket, db_session: Session) -> None:
    await notification_center.connect(user_id, websocket)
    try:
        # Send a small acknowledgement payload so clients know the socket is ready.
        await websocket.send_json({"type": "notification.connected"})
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    finally:
        await notification_center.disconnect(user_id, websocket)
