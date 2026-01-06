from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user, get_owners_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import ARCCondition, ARCInspection, ARCAttachment, ARCRequest, ARCReview, Owner, User
from ..schemas.schemas import (
    ARCConditionCreate,
    ARCConditionRead,
    ARCConditionResolve,
    ARCInspectionCreate,
    ARCInspectionRead,
    ARCAttachmentRead,
    ARCReviewCreate,
    ARCReviewerRead,
    ARCRequestCreate,
    ARCRequestRead,
    ARCRequestStatusUpdate,
    ARCRequestUpdate,
)
from ..services import arc as arc_service
from ..services import arc_reviews as arc_review_service
from ..services.audit import audit_log
from ..core.request_context import get_request_id

router = APIRouter(prefix="/arc", tags=["arc"])
logger = logging.getLogger(__name__)


def _request_log_context(request: Request, user: User, **extra) -> dict:
    return {
        "route": request.url.path,
        "request_id": get_request_id(request),
        "user_id": user.id,
        "roles": user.role_names,
        **extra,
    }


def _get_request_with_relations(db: Session, arc_request_id: int) -> Optional[ARCRequest]:
    return (
        db.query(ARCRequest)
        .options(
            joinedload(ARCRequest.owner),
            joinedload(ARCRequest.reviewer),
            joinedload(ARCRequest.applicant),
            joinedload(ARCRequest.attachments),
            joinedload(ARCRequest.conditions),
            joinedload(ARCRequest.inspections),
            joinedload(ARCRequest.reviews).joinedload(ARCReview.reviewer),
        )
        .get(arc_request_id)
    )


@router.get("/requests", response_model=List[ARCRequestRead])
def list_arc_requests(
    request: Request,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ARCRequest]:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER"}
    is_manager = user.has_any_role(*manager_roles)
    query = (
        db.query(ARCRequest)
        .options(
            joinedload(ARCRequest.owner),
            joinedload(ARCRequest.attachments),
            joinedload(ARCRequest.conditions),
            joinedload(ARCRequest.inspections),
            joinedload(ARCRequest.reviews).joinedload(ARCReview.reviewer),
        )
        .order_by(ARCRequest.created_at.desc(), ARCRequest.id.desc())
    )

    log_context = _request_log_context(
        request=request,
        user=user,
        status_filter=status_filter,
        is_manager=is_manager,
    )
    try:
        if user.has_role("HOMEOWNER") and not is_manager:
            linked_owners = get_owners_for_user(db, user)
            if not linked_owners:
                logger.info("ARC list skipped: no linked owners.", extra=log_context)
                return []
            owner_ids = [owner.id for owner in linked_owners]
            log_context["owner_ids"] = owner_ids
            query = query.filter(ARCRequest.owner_id.in_(owner_ids))
        else:
            if not is_manager:
                raise HTTPException(status_code=403, detail="Insufficient privileges for ARC requests.")

        if status_filter is not None:
            normalized_status = status_filter.strip().upper()
            if not normalized_status or normalized_status not in arc_service.ARC_STATES:
                raise HTTPException(status_code=400, detail="Invalid ARC status filter.")
            log_context["status_filter"] = normalized_status
            query = query.filter(ARCRequest.status == normalized_status)

        logger.info("Listing ARC requests.", extra=log_context)
        requests = query.all()
        return [request for request in requests if request.owner]
    except HTTPException:
        logger.warning("ARC list request rejected.", extra=log_context)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Failed to list ARC requests.", extra=log_context)
        raise HTTPException(status_code=500, detail="Unable to fetch ARC requests.") from exc


@router.post("/requests", response_model=ARCRequestRead, status_code=status.HTTP_201_CREATED)
def create_arc_request(
    payload: ARCRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER"}
    is_manager = user.has_any_role(*manager_roles)

    log_context = _request_log_context(
        request=request,
        user=user,
        is_manager=is_manager,
        payload_owner_id=payload.owner_id,
    )
    try:
        owner = get_owner_for_user(db, user) if user.has_role("HOMEOWNER") else None
        if user.has_role("HOMEOWNER") and not is_manager:
            linked_owners = get_owners_for_user(db, user)
            if not linked_owners:
                raise HTTPException(status_code=400, detail="Owner record not linked to user.")
            if payload.owner_id is None:
                if len(linked_owners) > 1:
                    raise HTTPException(
                        status_code=400,
                        detail="owner_id is required for homeowners with multiple addresses.",
                    )
                owner_id = linked_owners[0].id
                owner = linked_owners[0]
            else:
                owner = next((item for item in linked_owners if item.id == payload.owner_id), None)
                if not owner:
                    raise HTTPException(status_code=403, detail="Not permitted to submit for this address.")
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

        logger.info("Creating ARC request.", extra=log_context)
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
    except HTTPException:
        logger.warning("ARC create request rejected.", extra=log_context)
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to create ARC request.", extra=log_context)
        raise HTTPException(status_code=500, detail="Unable to create ARC request.") from exc


@router.get("/requests/{arc_request_id}", response_model=ARCRequestRead)
def get_arc_request(
    arc_request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ARCRequest:
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER"}
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
    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER"}
    is_manager = user.has_any_role(*manager_roles)
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if arc_request.status != "DRAFT":
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
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
) -> ARCRequest:
    arc_request = db.get(ARCRequest, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    manager_roles = {"ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER"}
    is_manager = user.has_any_role(*manager_roles)

    if user.has_role("HOMEOWNER") and not is_manager:
        owner = get_owner_for_user(db, user)
        if not owner or owner.id != arc_request.owner_id:
            raise HTTPException(status_code=403, detail="Not allowed to update this request.")
        if payload.target_status != "SUBMITTED":
            raise HTTPException(status_code=400, detail="Homeowners may only submit draft requests.")

    try:
        arc_service.transition_arc_request(
            session=db,
            arc_request=arc_request,
            actor=user,
            target_status=payload.target_status,
            reviewer_user_id=user.id if is_manager else None,
        )
        db.commit()
        db.refresh(arc_request)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    arc_request = _get_request_with_relations(db, arc_request.id)
    arc_review_service.maybe_send_decision_notification(db, arc_request)
    arc_request = _get_request_with_relations(db, arc_request.id)
    return arc_request


@router.get("/reviewers", response_model=List[ARCReviewerRead])
def list_arc_reviewers(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
) -> List[User]:
    return arc_review_service.get_eligible_reviewers(db)


@router.post("/requests/{arc_request_id}/reviews", response_model=ARCRequestRead)
def submit_arc_review(
    arc_request_id: int,
    payload: ARCReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
) -> ARCRequest:
    arc_request = _get_request_with_relations(db, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    try:
        arc_review_service.submit_review(
            session=db,
            arc_request=arc_request,
            reviewer=user,
            decision=payload.decision,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(arc_request)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    arc_request = _get_request_with_relations(db, arc_request.id)
    arc_review_service.maybe_send_decision_notification(db, arc_request)
    arc_request = _get_request_with_relations(db, arc_request.id)
    return arc_request


@router.post(
    "/requests/{arc_request_id}/reopen",
    response_model=ARCRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def reopen_arc_request(
    arc_request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
) -> ARCRequest:
    arc_request = _get_request_with_relations(db, arc_request_id)
    if not arc_request:
        raise HTTPException(status_code=404, detail="ARC request not found.")

    if arc_request.status not in {
        "APPROVED",
        "APPROVED_WITH_CONDITIONS",
        "DENIED",
        "COMPLETED",
        "ARCHIVED",
        "PASSED",
        "FAILED",
    }:
        raise HTTPException(status_code=400, detail="Only closed ARC requests can be reopened.")

    reopened = ARCRequest(
        owner_id=arc_request.owner_id,
        submitted_by_user_id=user.id,
        title=arc_request.title,
        project_type=arc_request.project_type,
        description=arc_request.description,
        status="IN_REVIEW",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(reopened)
    db.flush()

    for attachment in arc_request.attachments:
        db.add(
            ARCAttachment(
                arc_request_id=reopened.id,
                uploaded_by_user_id=attachment.uploaded_by_user_id,
                original_filename=attachment.original_filename,
                stored_filename=attachment.stored_filename,
                content_type=attachment.content_type,
                file_size=attachment.file_size,
            )
        )

    for condition in arc_request.conditions:
        if condition.condition_type != "REQUIREMENT":
            continue
        db.add(
            ARCCondition(
                arc_request_id=reopened.id,
                created_by_user_id=condition.created_by_user_id,
                condition_type=condition.condition_type,
                text=condition.text,
                status="OPEN",
            )
        )

    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="arc.request.reopen",
        target_entity_type="ARCRequest",
        target_entity_id=str(reopened.id),
        before={"source_request_id": arc_request.id, "status": arc_request.status},
        after={"status": reopened.status},
    )

    db.commit()

    reopened = _get_request_with_relations(db, reopened.id)
    return reopened


@router.post("/requests/{arc_request_id}/attachments", response_model=ARCAttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_arc_attachment(
    arc_request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
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
    user: User = Depends(require_roles("HOMEOWNER", "ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
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
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
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
    user: User = Depends(require_roles("ARC", "BOARD", "SYSADMIN", "SECRETARY", "TREASURER")),
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
