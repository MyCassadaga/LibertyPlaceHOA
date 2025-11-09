from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Dict, Iterable, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models.models import ARCCondition, ARCInspection, ARCAttachment, ARCRequest, User
from ..services.audit import audit_log
from ..services.storage import storage_service

ARC_STATES: Iterable[str] = (
    "DRAFT",
    "SUBMITTED",
    "IN_REVIEW",
    "REVISION_REQUESTED",
    "APPROVED",
    "APPROVED_WITH_CONDITIONS",
    "DENIED",
    "COMPLETED",
    "ARCHIVED",
)

ARC_TRANSITIONS: Dict[str, set[str]] = {
    "DRAFT": {"SUBMITTED", "ARCHIVED"},
    "SUBMITTED": {"IN_REVIEW", "ARCHIVED"},
    "IN_REVIEW": {"REVISION_REQUESTED", "APPROVED", "APPROVED_WITH_CONDITIONS", "DENIED"},
    "REVISION_REQUESTED": {"SUBMITTED", "ARCHIVED"},
    "APPROVED": {"COMPLETED", "ARCHIVED"},
    "APPROVED_WITH_CONDITIONS": {"COMPLETED", "ARCHIVED"},
    "DENIED": {"ARCHIVED"},
    "COMPLETED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

def add_attachment(
    session: Session,
    arc_request: ARCRequest,
    actor: User,
    file: UploadFile,
) -> ARCAttachment:
    suffix = Path(file.filename or "").suffix or ""
    stored_name = f"arc_{arc_request.id}_{secrets.token_hex(8)}{suffix}"
    file_bytes = file.file.read()
    stored = storage_service.save_file(f"arc/{stored_name}", file_bytes, content_type=file.content_type)

    attachment = ARCAttachment(
        arc_request_id=arc_request.id,
        uploaded_by_user_id=actor.id,
        original_filename=file.filename or stored_name,
        stored_filename=stored.public_path,
        content_type=file.content_type,
        file_size=len(file_bytes) if file_bytes else None,
    )
    session.add(attachment)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="arc.attachments.add",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        after={"attachment_id": attachment.id, "filename": attachment.original_filename},
    )
    return attachment


def add_condition(
    session: Session,
    arc_request: ARCRequest,
    actor: User,
    text: str,
    condition_type: str = "COMMENT",
) -> ARCCondition:
    condition = ARCCondition(
        arc_request_id=arc_request.id,
        created_by_user_id=actor.id,
        condition_type=condition_type,
        text=text,
    )
    session.add(condition)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="arc.conditions.add",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        after={"condition_id": condition.id, "type": condition_type},
    )
    return condition


def resolve_condition(
    session: Session,
    condition: ARCCondition,
    actor: User,
    status: str,
) -> ARCCondition:
    previous = condition.status
    condition.status = status
    condition.resolved_at = datetime.utcnow() if status == "RESOLVED" else None
    session.add(condition)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="arc.conditions.update",
        target_entity_type="ARCCondition",
        target_entity_id=str(condition.id),
        before={"status": previous},
        after={"status": status},
    )
    return condition


def add_inspection(
    session: Session,
    arc_request: ARCRequest,
    actor: User,
    scheduled_date: Optional[date],
    result: Optional[str],
    notes: Optional[str],
) -> ARCInspection:
    inspection = ARCInspection(
        arc_request_id=arc_request.id,
        inspector_user_id=actor.id,
        scheduled_date=scheduled_date,
        result=result,
        notes=notes,
    )
    session.add(inspection)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="arc.inspections.create",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        after={
            "inspection_id": inspection.id,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
            "result": result,
        },
    )
    return inspection


def transition_arc_request(
    session: Session,
    arc_request: ARCRequest,
    actor: User,
    target_status: str,
    reviewer_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> ARCRequest:
    if target_status not in ARC_STATES:
        raise ValueError("Invalid ARC status.")
    allowed = ARC_TRANSITIONS.get(arc_request.status, set())
    if target_status not in allowed:
        raise ValueError(f"Cannot transition from {arc_request.status} to {target_status}.")

    before_status = arc_request.status
    arc_request.status = target_status
    arc_request.updated_at = datetime.utcnow()

    if target_status == "SUBMITTED":
        arc_request.submitted_at = datetime.utcnow()
    if target_status == "REVISION_REQUESTED":
        arc_request.revision_requested_at = datetime.utcnow()
    if target_status in {"APPROVED", "APPROVED_WITH_CONDITIONS", "DENIED"}:
        arc_request.final_decision_at = datetime.utcnow()
        arc_request.final_decision_by_user_id = actor.id
        arc_request.decision_notes = notes
    if target_status == "COMPLETED":
        arc_request.completed_at = datetime.utcnow()
    if target_status == "ARCHIVED":
        arc_request.archived_at = datetime.utcnow()

    if reviewer_user_id:
        arc_request.reviewer_user_id = reviewer_user_id

    session.add(arc_request)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="arc.transition",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        before={"status": before_status},
        after={"status": target_status, "notes": notes, "reviewer_user_id": reviewer_user_id},
    )
    return arc_request
