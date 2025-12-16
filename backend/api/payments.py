from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..config import settings
from ..models.models import (
    AutopayEnrollment,
    Contract,
    Invoice,
    InvoiceStatus,
    Owner,
    Payment,
    User,
    VendorPayment,
)
from ..schemas.schemas import (
    AutopayEnrollmentRead,
    AutopayEnrollmentRequest,
    VendorPaymentCreate,
    VendorPaymentRead,
)
from ..services.audit import audit_log
from ..services.billing import record_payment

router = APIRouter()

BOARD_PAY_ROLES = ("BOARD", "TREASURER", "SYSADMIN")


class PaymentSessionRequest(BaseModel):
    invoiceId: int


@router.post("/session")
def create_payment_session(
    payload: PaymentSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    if not settings.stripe_api_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    stripe.api_key = settings.stripe_api_key

    invoice = db.get(Invoice, payload.invoiceId)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    owner = db.get(Owner, invoice.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found for invoice")
    if owner.is_archived:
        raise HTTPException(status_code=400, detail="Cannot pay invoices for an archived owner.")
    if invoice.status == InvoiceStatus.VOID:
        raise HTTPException(status_code=400, detail="Invoice is void")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    if user.has_role("HOMEOWNER"):
        owner_for_user = get_owner_for_user(db, user)
        if not owner_for_user or owner_for_user.id != invoice.owner_id:
            raise HTTPException(status_code=403, detail="Not authorized for this invoice")
    elif not user.has_any_role(*BOARD_PAY_ROLES):
        raise HTTPException(status_code=403, detail="Not authorized to initiate payments")

    amount_cents = _to_cents(invoice.amount)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Invoice amount must be greater than zero")

    metadata = {
        "invoice_id": str(invoice.id),
        "owner_id": str(owner.id),
        "initiated_by_user_id": str(user.id),
    }
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": f"HOA Invoice #{invoice.id}",
                            "description": owner.property_address or owner.mailing_address or "HOA assessment",
                        },
                    },
                    "quantity": 1,
                }
            ],
            customer_email=_get_customer_email(owner, user),
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            success_url=f"{settings.frontend_url}/billing?invoiceId={invoice.id}&payment=success",
            cancel_url=f"{settings.frontend_url}/billing?invoiceId={invoice.id}&payment=cancelled",
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail="Unable to create Stripe Checkout session") from exc

    return {"checkoutUrl": session.url}


def _to_cents(amount: Decimal) -> int:
    return int((Decimal(amount) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _get_customer_email(owner: Owner, user: User) -> Optional[str]:
    return owner.primary_email or owner.secondary_email or user.email


def _record_stripe_payment(
    db: Session,
    *,
    invoice_id: int,
    amount_cents: int,
    payment_intent_id: str,
    status: str = "succeeded",
) -> Optional[Payment]:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        return None
    owner = db.get(Owner, invoice.owner_id)
    if not owner or owner.is_archived:
        return None

    existing = (
        db.query(Payment)
        .filter(Payment.reference == payment_intent_id)
        .first()
    )
    if existing:
        return existing

    amount = (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))
    payment = Payment(
        owner_id=owner.id,
        invoice_id=invoice.id,
        amount=amount,
        method="stripe",
        reference=payment_intent_id,
        notes="Stripe Checkout",
    )
    db.add(payment)
    db.flush()
    record_payment(db, payment)
    if amount >= Decimal(invoice.amount):
        invoice.status = InvoiceStatus.PAID
        db.add(invoice)
    audit_log(
        db_session=db,
        actor_user_id=None,
        action=f"payments.stripe.{status}",
        target_entity_type="Payment",
        target_entity_id=str(payment.id),
        after={
            "invoice_id": invoice.id,
            "owner_id": owner.id,
            "amount": str(amount),
            "reference": payment_intent_id,
        },
    )
    db.commit()
    db.refresh(payment)
    return payment


def _handle_checkout_completed(db: Session, event_object: dict) -> None:
    metadata = event_object.get("metadata") or {}
    invoice_id = metadata.get("invoice_id")
    payment_intent_id = event_object.get("payment_intent")
    amount_total = event_object.get("amount_total")
    if not invoice_id or payment_intent_id is None or amount_total is None:
        return
    try:
        invoice_id_int = int(invoice_id)
        amount_cents = int(amount_total)
    except (TypeError, ValueError):
        return
    _record_stripe_payment(
        db=db,
        invoice_id=invoice_id_int,
        amount_cents=amount_cents,
        payment_intent_id=payment_intent_id,
        status="succeeded",
    )


def _handle_payment_intent(db: Session, event_object: dict) -> None:
    metadata = event_object.get("metadata") or {}
    invoice_id = metadata.get("invoice_id")
    payment_intent_id = event_object.get("id")
    amount_received = event_object.get("amount_received") or event_object.get("amount")
    status = event_object.get("status")
    if not invoice_id or payment_intent_id is None or amount_received is None:
        return
    try:
        invoice_id_int = int(invoice_id)
        amount_cents = int(amount_received)
    except (TypeError, ValueError):
        return
    if status == "succeeded":
        _record_stripe_payment(
            db=db,
            invoice_id=invoice_id_int,
            amount_cents=amount_cents,
            payment_intent_id=payment_intent_id,
            status="succeeded",
        )
    elif status == "requires_payment_method":
        audit_log(
            db_session=db,
            actor_user_id=None,
            action="payments.stripe.failed",
            target_entity_type="Invoice",
            target_entity_id=str(invoice_id),
            after={"reference": payment_intent_id},
        )
        db.commit()


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type")
    event_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, event_object)
    elif event_type in {"payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.processing"}:
        _handle_payment_intent(db, event_object)

    return {"received": True}


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
    enrollment.cancelled_at = datetime.now(timezone.utc)
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
    payment.provider_reference = f"SIM-{payment.id}-{int(datetime.now(timezone.utc).timestamp())}"
    payment.submitted_at = datetime.now(timezone.utc)
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
    payment.paid_at = datetime.now(timezone.utc)
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
