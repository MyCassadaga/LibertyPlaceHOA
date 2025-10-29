from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import LedgerEntry, Owner, OwnerUpdateRequest, User, Invoice, Payment
from ..schemas.schemas import (
    InvoiceRead,
    LedgerEntryRead,
    OwnerCreate,
    OwnerExport,
    OwnerRead,
    OwnerUpdate,
    OwnerUpdateRequestCreate,
    OwnerUpdateRequestRead,
    OwnerUpdateRequestReview,
    PaymentRead,
)
from ..services.audit import audit_log

router = APIRouter()


def _get_owner_or_404(db: Session, owner_id: int) -> Owner:
    owner = db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


def _collect_owner_export(db: Session, owner: Owner) -> OwnerExport:
    return _collect_owner_export(db, owner)


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


@router.get("/{owner_id}/export", response_model=OwnerExport)
def export_owner_data(
    owner_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OwnerExport:
    owner = _get_owner_or_404(db, owner_id)
    privileged_roles = {"BOARD", "TREASURER", "SECRETARY", "SYSADMIN", "AUDITOR"}

    if user.role and user.role.name == "HOMEOWNER":
        linked_owner = get_owner_for_user(db, user)
        if not linked_owner or linked_owner.id != owner_id:
            raise HTTPException(status_code=403, detail="Not allowed to export data for another owner")
    elif not user.role or user.role.name not in privileged_roles:
        raise HTTPException(status_code=403, detail="Role not permitted to export owner data")

    invoices = (
        db.query(Invoice)
        .filter(Invoice.owner_id == owner.id)
        .order_by(Invoice.created_at.asc())
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.owner_id == owner.id)
        .order_by(Payment.date_received.asc())
        .all()
    )
    ledger_entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.owner_id == owner.id)
        .order_by(LedgerEntry.timestamp.asc())
        .all()
    )
    update_requests = (
        db.query(OwnerUpdateRequest)
        .filter(OwnerUpdateRequest.owner_id == owner.id)
        .order_by(OwnerUpdateRequest.created_at.asc())
        .all()
    )

    return OwnerExport(
        owner=OwnerRead.from_orm(owner),
        invoices=[InvoiceRead.from_orm(invoice) for invoice in invoices],
        payments=[PaymentRead.from_orm(payment) for payment in payments],
        ledger_entries=[LedgerEntryRead.from_orm(entry) for entry in ledger_entries],
        update_requests=[OwnerUpdateRequestRead.from_orm(request) for request in update_requests],
    )


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


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_owner(
    owner_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Response:
    owner = _get_owner_or_404(db, owner_id)
    export_snapshot = _collect_owner_export(db, owner)
    audit_payload: Dict[str, object] = export_snapshot.dict()

    db.delete(owner)
    db.commit()

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.delete",
        target_entity_type="Owner",
        target_entity_id=str(owner_id),
        before=audit_payload,
        after=None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
