from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import AuditLog, User
from ..schemas.schemas import AuditLogActor, AuditLogEntry, AuditLogList

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/", response_model=AuditLogList)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("SYSADMIN", "AUDITOR")),
) -> AuditLogList:
    query = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.actor))
        .order_by(AuditLog.timestamp.desc())
    )
    total = query.count()
    logs = query.offset(offset).limit(limit).all()
    items = [
        AuditLogEntry(
            id=entry.id,
            timestamp=entry.timestamp,
            action=entry.action,
            target_entity_type=entry.target_entity_type,
            target_entity_id=entry.target_entity_id,
            before=entry.before,
            after=entry.after,
            actor=AuditLogActor(
                id=entry.actor.id if entry.actor else None,
                email=entry.actor.email if entry.actor else None,
                full_name=entry.actor.full_name if entry.actor else None,
            ),
        )
        for entry in logs
    ]
    return AuditLogList(items=items, total=total)
