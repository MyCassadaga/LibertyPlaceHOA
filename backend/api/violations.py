from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Appeal, FineSchedule, Owner, User, Violation, ViolationNotice
from ..schemas.schemas import (
    AppealCreate,
    AppealDecision,
    AppealRead,
    FineScheduleRead,
    ViolationCreate,
    ViolationRead,
    ViolationStatusUpdate,
    ViolationUpdate,
    ViolationNoticeRead,
)
from ..services.audit import audit_log
from ..services.violations import transition_violation, create_appeal

router = APIRouter()


def _serialize_violation(violation: Violation) -> ViolationRead:
    return ViolationRead.from_orm(violation)


@router.get("/fine-schedules", response_model=List[FineScheduleRead])
def list_fine_schedules(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> List[FineSchedule]:
    return db.query(FineSchedule).order_by(FineSchedule.name.asc()).all()


@router.get("/", response_model=List[ViolationRead])
def list_violations(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    owner_id: Optional[int] = None,
    mine: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[Violation]:
    query = (
        db.query(Violation)
        .options(
            joinedload(Violation.owner),
            joinedload(Violation.notices),
            joinedload(Violation.appeals),
        )
        .order_by(Violation.opened_at.desc())
    )

    manager_roles = {"BOARD", "TREASURER", "SYSADMIN", "ATTORNEY", "SECRETARY"}
    is_manager = user.has_any_role(*manager_roles)

    if is_manager:
        if mine:
            owner = get_owner_for_user(db, user)
            if owner:
                query = query.filter(Violation.owner_id == owner.id)
        elif owner_id:
            query = query.filter(Violation.owner_id == owner_id)
    else:
        owner = get_owner_for_user(db, user)
        if not owner:
            return []
        query = query.filter(Violation.owner_id == owner.id)

    if status_filter:
        query = query.filter(Violation.status == status_filter.upper())

    violations = query.all()
    return violations


@router.post("/", response_model=ViolationRead, status_code=status.HTTP_201_CREATED)
def create_violation(
    payload: ViolationCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> Violation:
    owner: Optional[Owner] = None
    placeholder_created = False

    if payload.owner_id:
        owner = db.get(Owner, payload.owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner not found.")
        if owner.is_archived:
            raise HTTPException(status_code=400, detail="Cannot file violations for an archived owner.")
    else:
        if not payload.user_id:
            raise HTTPException(status_code=400, detail="Owner or user must be specified.")
        target_user = db.get(User, payload.user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found.")
        owner = get_owner_for_user(db, target_user)
        if not owner:
            primary_name = target_user.full_name or target_user.email or "Resident"
            owner = Owner(
                primary_name=primary_name,
                lot=f"USER-{target_user.id:04d}",
                property_address=f"Pending address for {primary_name}",
                primary_email=target_user.email,
            )
            db.add(owner)
            db.flush()
            placeholder_created = True
        if owner.is_archived:
            raise HTTPException(status_code=400, detail="Cannot file violations for an archived owner.")

    if not owner:
        raise HTTPException(status_code=404, detail="Unable to resolve owner for violation.")

    violation = Violation(
        owner_id=owner.id,
        reported_by_user_id=actor.id,
        fine_schedule_id=payload.fine_schedule_id,
        status="NEW",
        category=payload.category,
        description=payload.description,
        location=payload.location,
        due_date=payload.due_date,
    )
    db.add(violation)
    db.commit()
    db.refresh(violation)

    if placeholder_created:
        audit_log(
            db_session=db,
            actor_user_id=actor.id,
            action="owner.placeholder_created",
            target_entity_type="Owner",
            target_entity_id=str(owner.id),
            after={
                "primary_name": owner.primary_name,
                "primary_email": owner.primary_email,
                "property_address": owner.property_address,
            },
        )

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="violations.create",
        target_entity_type="Violation",
        target_entity_id=str(violation.id),
        after={
            "owner_id": owner.id,
            "category": payload.category,
            "description": payload.description,
        },
    )

    violation = (
        db.query(Violation)
        .options(joinedload(Violation.owner), joinedload(Violation.notices), joinedload(Violation.appeals))
        .get(violation.id)
    )
    return violation


@router.get("/{violation_id}", response_model=ViolationRead)
def get_violation(
    violation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Violation:
    violation = (
        db.query(Violation)
        .options(
            joinedload(Violation.owner),
            joinedload(Violation.notices),
            joinedload(Violation.appeals),
        )
        .get(violation_id)
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found.")

    manager_roles = {"BOARD", "TREASURER", "SYSADMIN", "ATTORNEY", "SECRETARY"}
    if user.has_any_role(*manager_roles):
        return violation

    owner = get_owner_for_user(db, user)
    if not owner or owner.id != violation.owner_id:
        raise HTTPException(status_code=403, detail="Not allowed to view this violation.")

    return violation


@router.put("/{violation_id}", response_model=ViolationRead)
def update_violation(
    violation_id: int,
    payload: ViolationUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> Violation:
    violation = db.get(Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found.")

    before = {
        column.name: getattr(violation, column.name)
        for column in Violation.__table__.columns
        if column.name in {"category", "description", "location", "due_date", "hearing_date", "fine_amount", "resolution_notes"}
    }

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(violation, field, value)
    db.add(violation)
    db.commit()
    db.refresh(violation)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="violations.update",
        target_entity_type="Violation",
        target_entity_id=str(violation.id),
        before=before,
        after=payload.dict(exclude_unset=True),
    )

    violation = (
        db.query(Violation)
        .options(joinedload(Violation.owner), joinedload(Violation.notices), joinedload(Violation.appeals))
        .get(violation.id)
    )
    return violation


@router.post("/{violation_id}/transition", response_model=ViolationRead)
def transition_violation_status(
    violation_id: int,
    payload: ViolationStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> Violation:
    violation = db.get(Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found.")

    try:
        transition_violation(
            session=db,
            violation=violation,
            actor=actor,
            target_status=payload.target_status,
            note=payload.note,
            hearing_date=payload.hearing_date,
            fine_amount=payload.fine_amount,
        )
        db.commit()
        db.refresh(violation)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    violation = (
        db.query(Violation)
        .options(joinedload(Violation.owner), joinedload(Violation.notices), joinedload(Violation.appeals))
        .get(violation.id)
    )
    return violation


@router.get("/{violation_id}/notices", response_model=List[ViolationNoticeRead])
def list_violation_notices(
    violation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ViolationNotice]:
    notices = (
        db.query(ViolationNotice)
        .filter(ViolationNotice.violation_id == violation_id)
        .order_by(ViolationNotice.created_at.desc())
        .all()
    )
    violation = db.get(Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found.")

    manager_roles = {"BOARD", "TREASURER", "SYSADMIN", "ATTORNEY", "SECRETARY"}
    if user.has_any_role(*manager_roles):
        return notices

    owner = get_owner_for_user(db, user)
    if not owner or owner.id != violation.owner_id:
        raise HTTPException(status_code=403, detail="Not allowed to view notices.")

    return notices


@router.post("/{violation_id}/appeals", response_model=AppealRead, status_code=status.HTTP_201_CREATED)
def submit_appeal(
    violation_id: int,
    payload: AppealCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("HOMEOWNER", "BOARD", "TREASURER", "SYSADMIN", "SECRETARY")),
) -> Appeal:
    violation = db.get(Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found.")

    staff_roles = {"BOARD", "TREASURER", "SYSADMIN", "SECRETARY"}
    is_homeowner_only = user.has_role("HOMEOWNER") and not user.has_any_role(*staff_roles)
    owner = get_owner_for_user(db, user) if is_homeowner_only else db.get(Owner, violation.owner_id)
    if is_homeowner_only:
        if not owner or owner.id != violation.owner_id:
            raise HTTPException(status_code=403, detail="Cannot appeal violations for another owner.")
    if not owner:
        raise HTTPException(status_code=404, detail="Owner record not found for this violation.")

    appeal = create_appeal(db, violation, owner, payload.reason)
    db.commit()
    db.refresh(appeal)

    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="violations.appeal.submit",
        target_entity_type="Appeal",
        target_entity_id=str(appeal.id),
        after={"reason": payload.reason},
    )

    return appeal


@router.post("/{violation_id}/appeals/{appeal_id}/decision", response_model=AppealRead)
def decide_appeal(
    violation_id: int,
    appeal_id: int,
    payload: AppealDecision,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "SYSADMIN")),
) -> Appeal:
    appeal = (
        db.query(Appeal)
        .filter(Appeal.id == appeal_id, Appeal.violation_id == violation_id)
        .first()
    )
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found.")

    appeal.status = payload.status
    appeal.decision_notes = payload.decision_notes
    appeal.decided_at = datetime.now(timezone.utc)
    appeal.reviewed_by_user_id = actor.id
    db.add(appeal)
    db.commit()
    db.refresh(appeal)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="violations.appeal.decision",
        target_entity_type="Appeal",
        target_entity_id=str(appeal.id),
        after={
            "status": payload.status,
            "decision_notes": payload.decision_notes,
        },
    )

    return appeal
