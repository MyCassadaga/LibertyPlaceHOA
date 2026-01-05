from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import LedgerEntry, Owner, OwnerUpdateRequest, OwnerUserLink, User, Invoice, Payment
from ..schemas.schemas import (
    InvoiceRead,
    LedgerEntryRead,
    OwnerSelfUpdate,
    OwnerCreate,
    OwnerExport,
    OwnerRead,
    OwnerUpdate,
    OwnerArchiveRequest,
    OwnerRestoreRequest,
    OwnerLinkRequest,
    OwnerUpdateRequestCreate,
    OwnerUpdateRequestRead,
    OwnerUpdateRequestReview,
    PaymentRead,
    ResidentRead,
    UserRead,
)
from ..services.audit import audit_log
from ..services import notices as notice_service

router = APIRouter()


def _get_owner_or_404(db: Session, owner_id: int) -> Owner:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


def _collect_owner_export(db: Session, owner: Owner) -> OwnerExport:
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


@router.get("/", response_model=List[OwnerRead])
def list_owners(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> List[Owner]:
    query = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .order_by(Owner.property_address.asc())
    )
    if not include_archived:
        query = query.filter(Owner.is_archived.is_(False))
    return query.all()


@router.get("/residents", response_model=List[ResidentRead])
def list_residents(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> List[ResidentRead]:
    owners_query = (
        db.query(Owner)
        .options(
            joinedload(Owner.linked_users).joinedload(User.roles),
        )
        .order_by(Owner.property_address.asc())
    )
    if not include_archived:
        owners_query = owners_query.filter(Owner.is_archived.is_(False))
    owners = owners_query.all()

    users = (
        db.query(User)
        .options(joinedload(User.roles))
        .order_by(User.created_at.asc())
        .all()
    )

    residents: List[ResidentRead] = []
    linked_user_ids: Set[int] = set()

    for owner in owners:
        owner_read = OwnerRead.from_orm(owner)
        if owner.linked_users:
            for linked_user in owner.linked_users:
                residents.append(ResidentRead(user=UserRead.from_orm(linked_user), owner=owner_read))
                linked_user_ids.add(linked_user.id)
        else:
            residents.append(ResidentRead(user=None, owner=owner_read))

    for user in users:
        if user.id not in linked_user_ids:
            residents.append(ResidentRead(user=UserRead.from_orm(user), owner=None))

    return residents


@router.get("/me", response_model=OwnerRead)
def get_my_owner_record(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Owner:
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner record not linked to current user")
    return owner


@router.put("/me", response_model=OwnerRead)
def update_my_owner_record(
    payload: OwnerSelfUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Owner:
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner record not linked to current user")

    update_payload = payload.dict(exclude_unset=True)
    if not update_payload:
        return owner

    before = {field: getattr(owner, field) for field in update_payload.keys()}

    for field, value in update_payload.items():
        setattr(owner, field, value)

    db.add(owner)
    db.commit()
    db.refresh(owner)

    after = {field: getattr(owner, field) for field in update_payload.keys()}

    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="owner.self_update",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        before=before,
        after=after,
    )

    return owner


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
    try:
        notice_service.create_usps_welcome_notice(db, owner, actor)
        db.commit()
    except Exception:
        db.rollback()
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
    if user.has_role("HOMEOWNER"):
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

    if user.has_role("HOMEOWNER"):
        linked_owner = get_owner_for_user(db, user)
        if not linked_owner or linked_owner.id != owner_id:
            raise HTTPException(status_code=403, detail="Not allowed to export data for another owner")
    elif not user.has_any_role(*privileged_roles):
        raise HTTPException(status_code=403, detail="Role not permitted to export owner data")

    return _collect_owner_export(db, owner)


@router.put("/{owner_id}", response_model=OwnerRead)
def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")),
) -> Owner:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
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


def _get_linked_users(db: Session, owner_id: int) -> List[User]:
    return (
        db.query(User)
        .join(OwnerUserLink, OwnerUserLink.user_id == User.id)
        .filter(OwnerUserLink.owner_id == owner_id)
        .all()
    )


def _deactivate_linked_users(
    db: Session,
    owner: Owner,
    reason: Optional[str],
    archived_at: datetime,
) -> List[User]:
    linked_users = _get_linked_users(db, owner.id)
    if not linked_users:
        emails = {email.lower() for email in [owner.primary_email, owner.secondary_email] if email}
        if emails:
            linked_users = (
                db.query(User)
                .filter(func.lower(User.email).in_(emails))
                .all()
            )
    for user in linked_users:
        if user.is_active:
            user.is_active = False
            user.archived_at = archived_at
            address = owner.property_address or "Pending address"
            user.archived_reason = reason or f"Owner archived for property at {address}"
            db.add(user)
    return linked_users


def _reactivate_linked_users(
    db: Session,
    owner: Owner,
) -> List[User]:
    linked_users = _get_linked_users(db, owner.id)
    if not linked_users:
        emails = {email.lower() for email in [owner.primary_email, owner.secondary_email] if email}
        if emails:
            linked_users = (
                db.query(User)
                .filter(func.lower(User.email).in_(emails))
                .all()
            )
    for user in linked_users:
        if not user.is_active:
            user.is_active = True
            user.archived_at = None
            user.archived_reason = None
            db.add(user)
    return linked_users


@router.post("/{owner_id}/archive", response_model=OwnerRead)
def archive_owner(
    owner_id: int,
    payload: OwnerArchiveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Owner:
    owner = _get_owner_or_404(db, owner_id)
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Owner already archived.")

    archived_at = datetime.now(timezone.utc)
    original_lot = owner.lot

    before = OwnerRead.from_orm(owner).dict()

    if not owner.former_lot:
        owner.former_lot = original_lot

    owner.lot = f"{original_lot}-ARCHIVED-{owner.id}"
    owner.is_archived = True
    owner.archived_at = archived_at
    owner.archived_by_user_id = actor.id
    owner.archived_reason = payload.reason

    linked_users = _deactivate_linked_users(db, owner, payload.reason, archived_at)

    db.add(owner)
    db.commit()
    db.refresh(owner)

    after = OwnerRead.from_orm(owner).dict()
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.archive",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        before=before,
        after=after,
    )

    for user in linked_users:
        audit_log(
            db_session=db,
            actor_user_id=actor.id,
            action="user.deactivate",
            target_entity_type="User",
            target_entity_id=str(user.id),
            before={"is_active": True},
            after={"is_active": False, "archived_at": archived_at.isoformat()},
        )

    return owner


@router.post("/{owner_id}/restore", response_model=OwnerRead)
def restore_owner(
    owner_id: int,
    payload: OwnerRestoreRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Owner:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if not owner.is_archived:
        raise HTTPException(status_code=400, detail="Owner is not archived.")

    before = OwnerRead.from_orm(owner).dict()

    target_lot = owner.former_lot or owner.lot
    if target_lot:
        lot_conflict = (
            db.query(Owner)
            .filter(Owner.lot == target_lot)
            .filter(Owner.id != owner.id)
            .filter(Owner.is_archived.is_(False))
            .first()
        )
        if lot_conflict:
            raise HTTPException(
                status_code=400,
                detail="Cannot restore owner because another active owner uses this lot.",
            )
        owner.lot = target_lot

    owner.is_archived = False
    owner.archived_at = None
    owner.archived_by_user_id = None
    owner.archived_reason = None
    owner.former_lot = None

    reactivated_users: list[User] = []
    if payload.reactivate_user:
        reactivated_users = _reactivate_linked_users(db, owner)

    db.add(owner)
    db.commit()
    db.refresh(owner)

    after = OwnerRead.from_orm(owner).dict()
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.restore",
        target_entity_type="Owner",
        target_entity_id=str(owner.id),
        before=before,
        after=after,
    )

    for user in reactivated_users:
        audit_log(
            db_session=db,
            actor_user_id=actor.id,
            action="user.reactivate",
            target_entity_type="User",
            target_entity_id=str(user.id),
            before={"is_active": False},
            after={"is_active": True},
        )

    return owner


@router.post("/{owner_id}/link-user", response_model=OwnerRead)
def link_user_to_owner(
    owner_id: int,
    payload: OwnerLinkRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Owner:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.user_links).joinedload(OwnerUserLink.user).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot link users to an archived owner.")

    user = db.query(User).options(joinedload(User.roles)).get(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing_link = (
        db.query(OwnerUserLink)
        .filter(OwnerUserLink.owner_id == owner.id, OwnerUserLink.user_id == user.id)
        .first()
    )
    if existing_link:
        return OwnerRead.from_orm(owner)

    if user.has_role("HOMEOWNER"):
        conflict = (
            db.query(OwnerUserLink)
            .join(Owner, OwnerUserLink.owner_id == Owner.id)
            .filter(OwnerUserLink.user_id == user.id)
            .filter(Owner.id != owner.id)
            .filter(Owner.is_archived.is_(False))
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Homeowner account is already linked to another property.")

    link = OwnerUserLink(owner_id=owner.id, user_id=user.id, link_type=payload.link_type)
    db.add(link)
    db.commit()
    db.refresh(owner)

    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner.id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.link_user",
        target_entity_type="Owner",
        target_entity_id=str(owner_id),
        after={"user_id": user.id},
    )
    return owner


@router.delete("/{owner_id}/link-user/{user_id}", response_model=OwnerRead)
def unlink_user_from_owner(
    owner_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Owner:
    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    link = (
        db.query(OwnerUserLink)
        .filter(OwnerUserLink.owner_id == owner_id, OwnerUserLink.user_id == user_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    user = db.query(User).options(joinedload(User.roles)).get(user_id)
    if user and user.has_role("HOMEOWNER"):
        other_links = (
            db.query(OwnerUserLink)
            .join(Owner, OwnerUserLink.owner_id == Owner.id)
            .filter(OwnerUserLink.user_id == user_id, OwnerUserLink.owner_id != owner_id)
            .filter(Owner.is_archived.is_(False))
            .count()
        )
        if other_links == 0:
            # allow unlink but warn via audit log (optional) -- here we proceed
            pass

    db.delete(link)
    db.commit()

    owner = (
        db.query(Owner)
        .options(joinedload(Owner.linked_users).joinedload(User.roles))
        .get(owner_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="owner.unlink_user",
        target_entity_type="Owner",
        target_entity_id=str(owner_id),
        before={"user_id": user_id},
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
    if user.has_role("HOMEOWNER"):
        if user.email and user.email.lower() not in {
            (owner.primary_email or "").lower(),
            (owner.secondary_email or "").lower(),
        }:
            raise HTTPException(status_code=403, detail="May only propose changes for your own record")
    elif not user.has_any_role("BOARD", "SECRETARY", "SYSADMIN"):
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
    request.reviewed_at = datetime.now(timezone.utc)
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
