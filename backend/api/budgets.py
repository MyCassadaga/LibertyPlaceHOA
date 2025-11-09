import math
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import (
    Budget,
    BudgetApproval,
    BudgetAttachment,
    BudgetLineItem,
    ReservePlanItem,
    User,
)
from ..schemas.schemas import (
    BudgetApprovalRead,
    BudgetAttachmentCreateResponse,
    BudgetCreate,
    BudgetLineItemCreate,
    BudgetLineItemRead,
    BudgetLineItemUpdate,
    BudgetRead,
    BudgetSummary,
    BudgetUpdate,
    ReservePlanItemCreate,
    ReservePlanItemRead,
    ReservePlanItemUpdate,
)
from ..services import budgets as budget_service
from ..services.audit import audit_log
from ..services.notifications import create_notification
from ..services.storage import storage_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


EDIT_ROLES = ("BOARD", "TREASURER", "SYSADMIN")


def _ensure_editable(budget: Budget, user: User) -> None:
    if budget.status.upper() == "APPROVED" and not user.has_role("SYSADMIN"):
        raise HTTPException(status_code=400, detail="Budget is locked for editing")


def _require_board_member(user: User) -> None:
    if user.has_role("SYSADMIN"):
        return
    if not user.has_role("BOARD"):
        raise HTTPException(status_code=403, detail="Board approval required for this action")


def _approval_counts(budget: Budget) -> int:
    return len(budget.approvals)


def _serialize_budget(budget: Budget, db: Session, current_user: Optional[User] = None) -> BudgetRead:
    operations_total, reserves_total, total = budget_service.compute_totals(budget)
    assessment = budget_service.calculate_assessment(total, budget.home_count or 0)
    attachments = [
        BudgetAttachmentCreateResponse(
            id=attachment.id,
            file_name=attachment.file_name,
            stored_path=attachment.stored_path,
            content_type=attachment.content_type,
            file_size=attachment.file_size,
            uploaded_at=attachment.uploaded_at,
        )
        for attachment in budget.attachments
    ]
    approvals = [
        {
            "user_id": approval.user_id,
            "full_name": approval.user.full_name if approval.user else None,
            "email": approval.user.email if approval.user else None,
            "approved_at": approval.approved_at,
        }
        for approval in sorted(budget.approvals, key=lambda entry: entry.approved_at or datetime.utcnow())
    ]
    required = budget_service.calculate_required_board_approvals(db)
    user_has_approved = any(approval["user_id"] == current_user.id for approval in approvals) if current_user else False
    return BudgetRead(
        id=budget.id,
        year=budget.year,
        status=budget.status,
        home_count=budget.home_count,
        notes=budget.notes,
        locked_at=budget.locked_at,
        locked_by_user_id=budget.locked_by_user_id,
        total_annual=total,
        operations_total=operations_total,
        reserves_total=reserves_total,
        assessment_per_quarter=assessment,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
        line_items=[BudgetLineItemRead.from_orm(item) for item in budget.line_items],
        reserve_items=[ReservePlanItemRead.from_orm(item) for item in budget.reserve_items],
        attachments=attachments,
        approvals=[
            BudgetApprovalRead(
                user_id=entry["user_id"],
                full_name=entry["full_name"],
                email=entry["email"],
                approved_at=entry["approved_at"],
            )
            for entry in approvals
        ],
        approval_count=len(approvals),
        required_approvals=required,
        user_has_approved=user_has_approved,
    )


def _finalize_budget_lock(
    db: Session,
    budget: Budget,
    actor_user_id: Optional[int],
    trigger: str = "manual",
) -> None:
    if budget.status.upper() == "APPROVED":
        return
    budget.status = "APPROVED"
    budget.locked_at = datetime.utcnow()
    budget.locked_by_user_id = actor_user_id
    db.add(budget)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=actor_user_id,
        action=f"budget.lock.{trigger}",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
        after={"status": "APPROVED"},
    )
    _notify_homeowners_of_budget(db, budget)


def _notify_homeowners_of_budget(db: Session, budget: Budget) -> None:
    operations_total, reserves_total, total = budget_service.compute_totals(budget)
    assessment = budget_service.calculate_assessment(total, budget.home_count or 0)
    message = (
        f"The board approved the {budget.year} budget. "
        f"Quarterly assessments are now set to ${assessment} per home."
    )
    create_notification(
        db,
        title=f"{budget.year} Budget Approved",
        message=message,
        level="info",
        category="budget",
        link_url="/budget",
        role_names=["HOMEOWNER"],
    )
    db.commit()


def _clear_budget_approvals(db: Session, budget: Budget) -> None:
    db.query(BudgetApproval).filter(BudgetApproval.budget_id == budget.id).delete()
    db.commit()


@router.get("/", response_model=List[BudgetSummary])
def list_budgets(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> List[BudgetSummary]:
    budget_service.ensure_next_year_draft(db)
    query = (
        db.query(Budget)
        .options(joinedload(Budget.line_items))
        .order_by(Budget.year.desc())
    )
    if not user.has_any_role(*EDIT_ROLES):
        query = query.filter(Budget.status == "APPROVED")
    budgets = query.all()
    summaries: List[BudgetSummary] = []
    for budget in budgets:
        operations_total, reserves_total, total = budget_service.compute_totals(budget)
        assessment = budget_service.calculate_assessment(total, budget.home_count or 0)
        summaries.append(
            BudgetSummary(
                id=budget.id,
                year=budget.year,
                status=budget.status,
                total_annual=total,
                assessment_per_quarter=assessment,
            )
        )
    return summaries


@router.post("/", response_model=BudgetRead)
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetRead:
    existing = db.query(Budget).filter(Budget.year == payload.year).first()
    if existing:
        raise HTTPException(status_code=400, detail="A budget already exists for this year")
    budget = Budget(
        year=payload.year,
        home_count=payload.home_count or 0,
        notes=payload.notes,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.create",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
        after={"year": budget.year},
    )
    return _serialize_budget(budget, db, user)


@router.get("/{budget_id}", response_model=BudgetRead)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BudgetRead:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id)
        .options(
            joinedload(Budget.line_items),
            joinedload(Budget.reserve_items),
            joinedload(Budget.attachments),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status != "APPROVED" and not user.has_any_role(*EDIT_ROLES):
        raise HTTPException(status_code=403, detail="Budget not approved yet")
    return _serialize_budget(budget, db, user)


@router.patch("/{budget_id}", response_model=BudgetRead)
def update_budget(
    budget_id: int,
    payload: BudgetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetRead:
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_editable(budget, user)
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(budget, key, value)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.update",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
        after=data,
    )
    return _serialize_budget(budget, db, user)


@router.post("/{budget_id}/line-items", response_model=BudgetLineItemRead)
def add_line_item(
    budget_id: int,
    payload: BudgetLineItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetLineItemRead:
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_editable(budget, user)
    item = BudgetLineItem(
        budget_id=budget.id,
        label=payload.label,
        category=payload.category,
        amount=payload.amount,
        is_reserve=payload.is_reserve,
        sort_order=payload.sort_order or 0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.line_item.create",
        target_entity_type="BudgetLineItem",
        target_entity_id=str(item.id),
        after=payload.dict(),
    )
    return BudgetLineItemRead.from_orm(item)


@router.patch("/line-items/{item_id}", response_model=BudgetLineItemRead)
def update_line_item(
    item_id: int,
    payload: BudgetLineItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetLineItemRead:
    item = db.query(BudgetLineItem).filter(BudgetLineItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Budget line not found")
    _ensure_editable(item.budget, user)
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.line_item.update",
        target_entity_type="BudgetLineItem",
        target_entity_id=str(item.id),
        after=data,
    )
    return BudgetLineItemRead.from_orm(item)


@router.delete("/line-items/{item_id}", status_code=204)
def delete_line_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> None:
    item = db.query(BudgetLineItem).filter(BudgetLineItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Budget line not found")
    _ensure_editable(item.budget, user)
    db.delete(item)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.line_item.delete",
        target_entity_type="BudgetLineItem",
        target_entity_id=str(item_id),
    )


@router.post("/{budget_id}/reserve-items", response_model=ReservePlanItemRead)
def add_reserve_item(
    budget_id: int,
    payload: ReservePlanItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> ReservePlanItemRead:
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_editable(budget, user)
    item = ReservePlanItem(
        budget_id=budget.id,
        name=payload.name,
        target_year=payload.target_year,
        estimated_cost=payload.estimated_cost,
        inflation_rate=payload.inflation_rate,
        current_funding=payload.current_funding,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.reserve.create",
        target_entity_type="ReservePlanItem",
        target_entity_id=str(item.id),
        after=payload.dict(),
    )
    return ReservePlanItemRead.from_orm(item)


@router.patch("/reserve-items/{item_id}", response_model=ReservePlanItemRead)
def update_reserve_item(
    item_id: int,
    payload: ReservePlanItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> ReservePlanItemRead:
    item = db.query(ReservePlanItem).filter(ReservePlanItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Reserve plan item not found")
    _ensure_editable(item.budget, user)
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.reserve.update",
        target_entity_type="ReservePlanItem",
        target_entity_id=str(item.id),
        after=data,
    )
    return ReservePlanItemRead.from_orm(item)


@router.delete("/reserve-items/{item_id}", status_code=204)
def delete_reserve_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> None:
    item = db.query(ReservePlanItem).filter(ReservePlanItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Reserve plan item not found")
    _ensure_editable(item.budget, user)
    db.delete(item)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.reserve.delete",
        target_entity_type="ReservePlanItem",
        target_entity_id=str(item_id),
    )


@router.post("/{budget_id}/lock", response_model=BudgetRead)
def lock_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetRead:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id)
        .options(
            joinedload(Budget.line_items),
            joinedload(Budget.reserve_items),
            joinedload(Budget.attachments),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Budget already approved")
    if not budget.line_items:
        raise HTTPException(status_code=400, detail="Add at least one line item before locking")
    if not user.has_role("SYSADMIN"):
        _require_board_member(user)
        required = budget_service.calculate_required_board_approvals(db)
        approval_count = _approval_counts(budget)
        if required > 0 and approval_count < required:
            raise HTTPException(
                status_code=400,
                detail=f"{approval_count}/{required} approvals recorded. Two-thirds of board members must approve before locking.",
            )
    _finalize_budget_lock(db, budget, user.id, trigger="manual")
    db.refresh(budget)
    return _serialize_budget(budget, db, user)


@router.post("/{budget_id}/attachments", response_model=BudgetAttachmentCreateResponse)
def upload_budget_attachment(
    budget_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> BudgetAttachmentCreateResponse:
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_editable(budget, user)
    contents = file.file.read()
    stored = storage_service.save_file(
        f"budgets/{budget.year}/{file.filename}",
        contents,
        content_type=file.content_type,
    )
    attachment = BudgetAttachment(
        budget_id=budget.id,
        file_name=file.filename or stored.relative_path.split("/")[-1],
        stored_path=stored.public_path,
        content_type=file.content_type,
        file_size=len(contents),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.attachment.upload",
        target_entity_type="BudgetAttachment",
        target_entity_id=str(attachment.id),
    )
    return BudgetAttachmentCreateResponse.from_orm(attachment)


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_budget_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
) -> None:
    attachment = db.query(BudgetAttachment).filter(BudgetAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    budget = attachment.budget
    _ensure_editable(budget, user)
    storage_service.delete_file(attachment.stored_path)
    db.delete(attachment)
    db.commit()


@router.post("/{budget_id}/approve", response_model=BudgetRead)
def approve_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BudgetRead:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id)
        .options(
            joinedload(Budget.line_items),
            joinedload(Budget.reserve_items),
            joinedload(Budget.attachments),
            joinedload(Budget.approvals).joinedload(BudgetApproval.user),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Budget already approved")
    if not budget.line_items:
        raise HTTPException(status_code=400, detail="Add at least one line item before approvals can be recorded")
    _require_board_member(user)
    already = (
        db.query(BudgetApproval)
        .filter(BudgetApproval.budget_id == budget.id, BudgetApproval.user_id == user.id)
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="You have already approved this budget.")
    approval = BudgetApproval(budget_id=budget.id, user_id=user.id)
    db.add(approval)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.approval.create",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
    )
    db.refresh(budget)
    required = budget_service.calculate_required_board_approvals(db)
    if required > 0 and _approval_counts(budget) >= required:
        _finalize_budget_lock(db, budget, user.id, trigger="auto")
        db.refresh(budget)
    return _serialize_budget(budget, db, user)


@router.delete("/{budget_id}/approve", response_model=BudgetRead)
def revoke_budget_approval(
    budget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BudgetRead:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id)
        .options(
            joinedload(Budget.line_items),
            joinedload(Budget.reserve_items),
            joinedload(Budget.attachments),
            joinedload(Budget.approvals).joinedload(BudgetApproval.user),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Budget already locked. Ask a sysadmin to unlock.")
    _require_board_member(user)
    approval = (
        db.query(BudgetApproval)
        .filter(BudgetApproval.budget_id == budget.id, BudgetApproval.user_id == user.id)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=400, detail="You have not yet approved this budget.")
    db.delete(approval)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.approval.revoke",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
    )
    db.refresh(budget)
    return _serialize_budget(budget, db, user)


@router.post("/{budget_id}/unlock", response_model=BudgetRead)
def unlock_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("SYSADMIN")),
) -> BudgetRead:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id)
        .options(
            joinedload(Budget.line_items),
            joinedload(Budget.reserve_items),
            joinedload(Budget.attachments),
            joinedload(Budget.approvals),
        )
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget.status = "DRAFT"
    budget.locked_at = None
    budget.locked_by_user_id = None
    _clear_budget_approvals(db, budget)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="budget.unlock",
        target_entity_type="Budget",
        target_entity_id=str(budget.id),
        after={"status": "DRAFT"},
    )
    return _serialize_budget(budget, db, user)
