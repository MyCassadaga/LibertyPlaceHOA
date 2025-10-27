import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models.models import AuditLog


def _serialize(data: Any) -> Optional[str]:
    if data is None:
        return None
    try:
        return json.dumps(data, default=str)
    except TypeError:
        return str(data)


def audit_log(
    db_session: Session,
    actor_user_id: Optional[int],
    action: str,
    target_entity_type: Optional[str] = None,
    target_entity_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
) -> AuditLog:
    entry = AuditLog(
        timestamp=datetime.utcnow(),
        actor_user_id=actor_user_id,
        action=action,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        before=_serialize(before),
        after=_serialize(after),
    )
    db_session.add(entry)
    db_session.commit()
    return entry
