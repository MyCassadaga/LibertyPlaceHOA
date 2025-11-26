from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import ARCCondition, ARCInspection, ARCAttachment, ARCRequest, Owner, User
from ..schemas.schemas import (
    ARCConditionCreate,
    ARCConditionRead,
    ARCConditionResolve,
    ARCInspectionCreate,
    ARCInspectionRead,
    ARCAttachmentRead,
    ARCRequestCreate,
    ARCRequestRead,
    ARCRequestStatusUpdate,
    ARCRequestUpdate,
)
from ..services import arc as arc_service
from ..services.audit import audit_log

router = APIRouter(prefix="/arc", tags=["arc"])


def _get_request_with_relations(db: Session, arc_request_id: int) -> Optional[ARCRequest]:
    return (
        db.query(ARCRequest)
        .options(
            joinedload(ARCRequest.owner),
            joinedload(ARCRequest.attachments),
            joinedload(ARCRequest.conditions),
            joinedload(ARCRequest.inspections),
        )
        .get(arc_request_id)
    )


@router.get("/requests", response_model=List[ARCRequestRead])
def list_arc_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ARCRequest]:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)
    query = (
        db.query(ARCRequest)
        .options(
            joinedload(ARCRequest.owner),
            joinedload(ARCRequest.attachments),
            joinedload(ARCRequest.conditions),
            joinedload(ARCRequest.inspections),
        )
        .order_by(ARCRequest.created_at.desc())
    )

    if user.has_role("HOMEOWNER") and not is_manager:
        owner = get_owner_for_user(db, user)
        if not owner:
            return []
        query = query.filter(ARCRequest.owner_id == owner.id)
    else:
        if not is_manager:
            raise HTTPException(status_code=403, detail="Insufficient privileges for ARC requests.")

    if status_filter:
        query = query.filter(ARCRequest.status == status_filter.upper())

    return query.all()


@router.post("/requests", response_model=ARCRequestRead, status_code=status.HTTP_201_CREATED)
def create_arc_request(
    payload: ARCRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY")),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)

    owner = get_owner_for_user(db, user) if user.has_role("HOMEOWNER") else None
    if user.has_role("HOMEOWNER") and not is_manager:
        if not owner:
            raise HTTPException(status_code=400, detail="Owner record not linked to user.")
        owner_id = owner.id
    else:
        if not payload.owner_id:
            raise HTTPException(status_code=400, detail="owner_id is required for staff submissions.")
        owner = db.get(Owner, payload.owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner not found.")
        if owner.is_archived:
            raise HTTPException(status_code=400, detail="Cannot create ARC requests for an archived owner.")
        owner_id = owner.id

    arc_request = ARCRequest(
        owner_id=owner_id,
        submitted_by_user_id=user.id,
        title=payload.title,
        project_type=payload.project_type,
        description=payload.description,
        status="DRAFT",
    )
    db.add(arc_request)
    db.commit()
    db.refresh(arc_request)

    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="arc.request.create",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        after=payload.dict(),
    )

    arc_request = _get_request_with_relations(db, arc_request.id)
    return arc_request


@router.get("/requests/{arc_request_id}", response_model=ARCRequestRead)
def get_arc_request(
    arc_request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)
    arc_request = _get_request_with_relations(db, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if user.has_role("HOMEOWNER") and not is_manager:
        owner = get_owner_for_user(db, user)
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not permitted to view this request.")
    else:
        if not is_manager:
            raise HTTPException(status_code=403, detail="Not permitted to view this request.")

    return arc_request


@router.put("/requests/{arc_request_id}", response_model=ARCRequestRead)
def update_arc_request(
    arc_request_id: int,
    payload: ARCRequestUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if arc_request.status not in {"DRAFT", "REVISION_REQUESTED"}:
        raise HTTPException(status_code=400, detail="Cannot update request once in review.")

    owner = get_owner_for_user(db, user) if user.has_role("HOMEOWNER") else None
    if user.has_role("HOMEOWNER") and not is_manager:
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not permitted to modify this request.")
    else:
        if not is_manager:
            raise HTTPException(status_code=403, detail="Not permitted to update this request.")

    before = {
        column.name: getattr(arc_request, column.name)
        for column in ARCRequest.__table__.columns
        if column.name in {"title", "project_type", "description"}
    }

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(arc_request, field, value)

    db.add(arc_request)
    db.commit()
    db.refresh(arc_request)

    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="arc.request.update",
        target_entity_type="ARCRequest",
        target_entity_id=str(arc_request.id),
        before=before,
        after=payload.dict(exclude_unset=True),
    )

    arc_request = _get_request_with_relations(db, arc_request.id)
    return arc_request


@router.post("/requests/{arc_request_id}/status", response_model=ARCRequestRead)
def transition_arc_request_status(
    arc_request_id: int,
    payload: ARCRequestStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "HOMEOWNER")),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if user.has_role("HOMEOWNER") and not is_manager:
        owner = get_owner_for_user(db, user)
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not permitted for this request.")
        if payload.target_status not in {"SUBMITTED", "ARCHIVED"}:
            raise HTTPException(status_code=403, detail="Homeowners may only submit or archive their own requests.")

    try:
        arc_service.transition_arc_request(
            session=db,
            arc_request=arc_request,
            actor=user,
            target_status=payload.target_status,
            reviewer_user_id=payload.reviewer_user_id,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(arc_request)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    arc_request = _get_request_with_relations(db, arc_request.id)
    return arc_request


@router.post("/requests/{arc_request_id}/attachments", response_model=ARCAttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_arc_attachment(
    arc_request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY")),
) -> ARCAttachment:
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if user.has_role("HOMEOWNER"):
        owner = get_owner_for_user(db, user)
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not permitted to upload files for this request.")

    attachment = arc_service.add_attachment(db, arc_request, user, file)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.post("/requests/{arc_request_id}/conditions", response_model=ARCConditionRead, status_code=status.HTTP_201_CREATED)
def add_arc_condition(
    arc_request_id: int,
    payload: ARCConditionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY")),
) -> ARCCondition:
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if user.has_role("HOMEOWNER"):
        owner = get_owner_for_user(db, user)
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not permitted to comment on this request.")

    condition = arc_service.add_condition(db, arc_request, user, payload.text, payload.condition_type)
    db.commit()
    db.refresh(condition)
    return condition


@router.post("/requests/{arc_request_id}/conditions/{condition_id}/resolve", response_model=ARCConditionRead)
def resolve_arc_condition(
    arc_request_id: int,
    condition_id: int,
    payload: ARCConditionResolve,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY")),
) -> ARCCondition:
    condition = (
        db.query(ARCCondition)
        .filter(ARCCondition.id == condition_id, ARCCondition.arc_request_id == arc_request_id)
        .first()
    )
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found.")

    arc_service.resolve_condition(db, condition, user, payload.status)
    db.commit()
    db.refresh(condition)
    return condition


@router.post("/requests/{arc_request_id}/inspections", response_model=ARCInspectionRead, status_code=status.HTTP_201_CREATED)
def create_arc_inspection(
    arc_request_id: int,
    payload: ARCInspectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY")),
) -> ARCInspection:
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    inspection = arc_service.add_inspection(
        db,
        arc_request,
        user,
        scheduled_date=payload.scheduled_date,
        result=payload.result,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(inspection)
    return inspection
