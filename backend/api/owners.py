from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Owner, OwnerUpdateRequest, User
from ..schemas.schemas import (
    OwnerCreate,
    OwnerRead,
    OwnerUpdate,
    OwnerUpdateRequestCreate,
    OwnerUpdateRequestRead,
    OwnerUpdateRequestReview,
)
from ..services.audit import audit_log

router = APIRouter()


def _get_owner_or_404(db: Session, owner_id: int) -> Owner:
    owner = db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


@router.get("/", response_model=List[OwnerRead])
def list_owners(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> List[Owner]:
    return db.query(Owner).order_by(Owner.lot.asc()).all()


@router.post("/", response_model=OwnerRead)
def create_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Owner:
    owner = Owner(**payload.dict())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.create",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        after=payload.dict(),
    )
    return owner


@router.get("/{owner_id}", response_model=OwnerRead)
def get_owner(
    owner_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Owner:
    owner = _get_owner_or_404(db, owner_id)
    if user.role and user.role.name == "HOMEOWNER":
        if user.email and user.email.lower() not in {  # type: ignore[arg-type]
            (owner.primary_email or "").lower(),
            (owner.secondary_email or "").lower(),
        }:
            raise HTTPException(status_code=403, detail="Not allowed to view this owner")
    return owner


@router.put("/{owner_id}", response_model=OwnerRead)
def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> Owner:
    owner = _get_owner_or_404(db, owner_id)
    before = {column.name: getattr(owner, column.name) for column in Owner.__table__.columns}
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(owner, field, value)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    after = {column.name: getattr(owner, column.name) for column in Owner.__table__.columns}
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.update",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        before=before,
        after=after,
    )
    return owner


@router.post("/{owner_id}/proposals", response_model=OwnerUpdateRequestRead)
def propose_owner_update(
    owner_id: int,
    payload: OwnerUpdateRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OwnerUpdateRequest:
    owner = _get_owner_or_404(db, owner_id)
    if user.role and user.role.name == "HOMEOWNER":
        if user.email and user.email.lower() not in {
            (owner.primary_email or "").lower(),
            (owner.secondary_email or "").lower(),
        }:
            raise HTTPException(status_code=403, detail="May only propose changes for your own record")
    elif user.role and user.role.name not in {"BOARD", "SECRETARY", "SYSADMIN"}:
        raise HTTPException(status_code=403, detail="Role not allowed to propose changes")

    request = OwnerUpdateRequest(
        owner_id=owner.id,
        proposed_by_user_id=user.id,
        proposed_changes=payload.proposed_changes,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="owner.proposal",
        target_entity_type="OwnerUpdateRequest",
        target_entity_id=str(request.id),
        after=payload.proposed_changes,
    )
    return request


@router.get("/me", response_model=OwnerRead)
def get_my_owner_record(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Owner:
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner record not linked to current user")
    return owner


@router.get("/proposals/pending", response_model=List[OwnerUpdateRequestRead])
def list_pending_proposals(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> List[OwnerUpdateRequest]:
    return (
        db.query(OwnerUpdateRequest)
        .filter(OwnerUpdateRequest.status == "PENDING")
        .order_by(OwnerUpdateRequest.created_at.asc())
        .all()
    )


@router.post("/proposals/{request_id}/review", response_model=OwnerUpdateRequestRead)
def review_proposal(
    request_id: int,
    payload: OwnerUpdateRequestReview,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SECRETARY", "SYSADMIN")),
) -> OwnerUpdateRequest:
    request = db.get(OwnerUpdateRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if request.status != "PENDING":
        raise HTTPException(status_code=400, detail="Proposal already reviewed")

    owner = _get_owner_or_404(db, request.owner_id)
    before = {column.name: getattr(owner, column.name) for column in Owner.__table__.columns}

    if payload.status == "APPROVED":
        for field, value in request.proposed_changes.items():
            if hasattr(owner, field):
                setattr(owner, field, value)
        db.add(owner)

    request.status = payload.status
    request.reviewer_user_id = actor.id
    request.reviewed_at = datetime.utcnow()
    db.add(request)
    db.commit()
    db.refresh(request)
    db.refresh(owner)

    after = {column.name: getattr(owner, column.name) for column in Owner.__table__.columns}
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action=f"owner.proposal.{payload.status.lower()}",
        target_entity_type="OwnerUpdateRequest",
        target_entity_id=str(request.id),
        before=before,
        after=after,
    )
    return request
