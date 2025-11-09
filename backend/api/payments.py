from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import AutopayEnrollment, Contract, Owner, User, VendorPayment
from ..schemas.schemas import (
    AutopayEnrollmentRead,
    AutopayEnrollmentRequest,
    VendorPaymentCreate,
    VendorPaymentRead,
)
from ..services.audit import audit_log

router = APIRouter()

BOARD_PAY_ROLES = ("BOARD", "TREASURER", "SYSADMIN")


class PaymentSessionRequest(BaseModel):
    invoiceId: int


@router.post("/session")
def create_payment_session(_: PaymentSessionRequest) -> dict[str, str]:
    return {"checkoutUrl": "/billing?mock-payment-success=true"}


def _serialize_autopay(owner_id: int, enrollment: Optional[AutopayEnrollment]) -> AutopayEnrollmentRead:
    if not enrollment:
        return AutopayEnrollmentRead(
            owner_id=owner_id,
            status="NOT_ENROLLED",
            payment_day=None,
            amount_type="STATEMENT_BALANCE",
            fixed_amount=None,
            funding_source_mask=None,
            provider="STRIPE",
            provider_status="NOT_CONFIGURED",
            provider_setup_required=True,
            last_run_at=None,
            created_at=None,
            updated_at=None,
        )
    return AutopayEnrollmentRead(
        owner_id=enrollment.owner_id,
        status=enrollment.status,
        payment_day=enrollment.payment_day,
        amount_type=enrollment.amount_type,
        fixed_amount=enrollment.fixed_amount,
        funding_source_mask=enrollment.funding_source_mask,
        provider="STRIPE",
        provider_status=enrollment.provider_status or enrollment.status,
        provider_setup_required=enrollment.stripe_payment_method_id is None,
        last_run_at=enrollment.last_run_at,
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
    )


def _resolve_owner(
    db: Session,
    user: User,
    owner_id: Optional[int],
) -> Owner:
    if owner_id:
        owner = db.get(Owner, owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner not found")
        if user.has_any_role(*BOARD_PAY_ROLES):
            return owner
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != owner_id:
            raise HTTPException(status_code=403, detail="Not authorized for this owner")
        return owner
    owner = get_owner_for_user(db, user)
    if not owner:
        raise HTTPException(status_code=404, detail="Linked owner record not found")
    return owner


@router.get("/autopay", response_model=AutopayEnrollmentRead)
def get_autopay_enrollment(
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutopayEnrollmentRead:
    owner = _resolve_owner(db, user, owner_id)
    enrollment = (
        db.query(AutopayEnrollment)
        .filter(AutopayEnrollment.owner_id == owner.id)
        .first()
    )
    return _serialize_autopay(owner.id, enrollment)


@router.post("/autopay", response_model=AutopayEnrollmentRead)
def upsert_autopay_enrollment(
    payload: AutopayEnrollmentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutopayEnrollmentRead:
    owner = _resolve_owner(db, user, payload.owner_id)
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot manage autopay for an archived owner.")
    enrollment = (
        db.query(AutopayEnrollment)
        .filter(AutopayEnrollment.owner_id == owner.id)
        .first()
    )
    if not enrollment:
        enrollment = AutopayEnrollment(
            owner_id=owner.id,
            user_id=user.id,
        )
    enrollment.payment_day = payload.payment_day
    enrollment.amount_type = payload.amount_type
    enrollment.fixed_amount = payload.fixed_amount
    enrollment.status = "PENDING"
    enrollment.provider_status = "PENDING_PROVIDER"
    enrollment.cancelled_at = None
    enrollment.paused_at = None
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="payments.autopay.upsert",
        target_entity_type="AutopayEnrollment",
        target_entity_id=str(enrollment.id),
        after={
            "payment_day": payload.payment_day,
            "amount_type": payload.amount_type,
            "fixed_amount": str(payload.fixed_amount) if payload.fixed_amount else None,
        },
    )
    return _serialize_autopay(owner.id, enrollment)


@router.delete("/autopay", response_model=AutopayEnrollmentRead)
def cancel_autopay_enrollment(
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutopayEnrollmentRead:
    owner = _resolve_owner(db, user, owner_id)
    enrollment = (
        db.query(AutopayEnrollment)
        .filter(AutopayEnrollment.owner_id == owner.id)
        .first()
    )
    if not enrollment:
        return _serialize_autopay(owner.id, None)
    enrollment.status = "CANCELLED"
    enrollment.provider_status = "CANCELLED"
    enrollment.cancelled_at = datetime.utcnow()
    db.add(enrollment)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="payments.autopay.cancel",
        target_entity_type="AutopayEnrollment",
        target_entity_id=str(enrollment.id),
    )
    return _serialize_autopay(owner.id, enrollment)


def _serialize_vendor_payment(payment: VendorPayment) -> VendorPaymentRead:
    return VendorPaymentRead(
        id=payment.id,
        contract_id=payment.contract_id,
        vendor_name=payment.vendor_name,
        amount=payment.amount,
        memo=payment.memo,
        status=payment.status,
        provider=payment.provider,
        provider_status=payment.provider_status,
        provider_reference=payment.provider_reference,
        requested_at=payment.requested_at,
        submitted_at=payment.submitted_at,
        paid_at=payment.paid_at,
    )


def _get_vendor_payment(db: Session, payment_id: int) -> VendorPayment:
    payment = db.get(VendorPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Vendor payment not found")
    return payment


@router.get("/vendors", response_model=List[VendorPaymentRead])
def list_vendor_payments(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*BOARD_PAY_ROLES)),
) -> List[VendorPaymentRead]:
    payments = db.query(VendorPayment).order_by(VendorPayment.requested_at.desc()).all()
    return [_serialize_vendor_payment(payment) for payment in payments]


@router.post("/vendors", response_model=VendorPaymentRead)
def create_vendor_payment(
    payload: VendorPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_PAY_ROLES)),
) -> VendorPaymentRead:
    contract = None
    vendor_name = payload.vendor_name
    if payload.contract_id:
        contract = db.get(Contract, payload.contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        vendor_name = vendor_name or contract.vendor_name
    if not vendor_name:
        raise HTTPException(status_code=400, detail="Vendor name is required")
    payment = VendorPayment(
        contract_id=contract.id if contract else None,
        vendor_name=vendor_name,
        amount=payload.amount,
        memo=payload.memo,
        requested_by_user_id=user.id,
        status="PENDING",
        provider_status="PENDING_PROVIDER",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="payments.vendor.create",
        target_entity_type="VendorPayment",
        target_entity_id=str(payment.id),
        after={
            "vendor_name": vendor_name,
            "amount": str(payload.amount),
            "contract_id": contract.id if contract else None,
        },
    )
    return _serialize_vendor_payment(payment)


@router.post("/vendors/{payment_id}/send", response_model=VendorPaymentRead)
def submit_vendor_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_PAY_ROLES)),
) -> VendorPaymentRead:
    payment = _get_vendor_payment(db, payment_id)
    if payment.status not in {"PENDING", "FAILED"}:
        return _serialize_vendor_payment(payment)
    payment.status = "SUBMITTED"
    payment.provider_status = "QUEUED"
    payment.provider_reference = f"SIM-{payment.id}-{int(datetime.utcnow().timestamp())}"
    payment.submitted_at = datetime.utcnow()
    db.add(payment)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="payments.vendor.submit",
        target_entity_type="VendorPayment",
        target_entity_id=str(payment.id),
        after={"provider_reference": payment.provider_reference},
    )
    return _serialize_vendor_payment(payment)


@router.post("/vendors/{payment_id}/mark-paid", response_model=VendorPaymentRead)
def mark_vendor_payment_paid(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_PAY_ROLES)),
) -> VendorPaymentRead:
    payment = _get_vendor_payment(db, payment_id)
    if payment.status == "PAID":
        return _serialize_vendor_payment(payment)
    payment.status = "PAID"
    payment.provider_status = "PAID"
    payment.paid_at = datetime.utcnow()
    db.add(payment)
    db.commit()
    audit_log(
        db_session=db,
        actor_user_id=user.id,
        action="payments.vendor.mark_paid",
        target_entity_type="VendorPayment",
        target_entity_id=str(payment.id),
    )
    return _serialize_vendor_payment(payment)
