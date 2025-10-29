from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, confloat, condecimal, conint


class PermissionRead(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class RoleRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    permissions: List[PermissionRead] = []

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str]
    password: str = Field(min_length=8)
    role_id: int


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    role: RoleRead
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int


class OwnerBase(BaseModel):
    primary_name: str
    secondary_name: Optional[str]
    lot: str
    property_address: str
    mailing_address: Optional[str]
    primary_email: Optional[EmailStr]
    secondary_email: Optional[EmailStr]
    primary_phone: Optional[str]
    secondary_phone: Optional[str]
    occupancy_status: Optional[str]
    emergency_contact: Optional[str]
    is_rental: Optional[bool] = False
    lease_document_path: Optional[str]
    notes: Optional[str]


class OwnerCreate(OwnerBase):
    primary_name: str
    lot: str
    property_address: str


class OwnerUpdate(OwnerBase):
    pass


class OwnerRead(OwnerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class OwnerUpdateRequestCreate(BaseModel):
    proposed_changes: Dict[str, Any]


class OwnerUpdateRequestReview(BaseModel):
    status: str = Field(..., regex="^(APPROVED|REJECTED)$")


class OwnerUpdateRequestRead(BaseModel):
    id: int
    owner_id: int
    proposed_by_user_id: int
    proposed_changes: Dict[str, Any]
    status: str
    reviewer_user_id: Optional[int]
    created_at: datetime
    reviewed_at: Optional[datetime]

    class Config:
        orm_mode = True


class InvoiceBase(BaseModel):
    owner_id: int
    lot: Optional[str]
    amount: Decimal
    due_date: date
    notes: Optional[str]
    original_amount: Optional[Decimal]


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    status: Optional[str]
    notes: Optional[str]
    late_fee_applied: Optional[bool]


class InvoiceRead(BaseModel):
    id: int
    owner_id: int
    lot: Optional[str]
    amount: Decimal
    original_amount: Decimal
    late_fee_total: Decimal
    due_date: date
    status: str
    late_fee_applied: bool
    notes: Optional[str]
    last_late_fee_applied_at: Optional[datetime]
    last_reminder_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PaymentCreate(BaseModel):
    owner_id: int
    invoice_id: Optional[int]
    amount: Decimal
    method: Optional[str]
    reference: Optional[str]
    notes: Optional[str]


class LateFeePayload(BaseModel):
    fee_amount: Decimal


class BillingPolicyRead(BaseModel):
    name: str
    grace_period_days: int
    dunning_schedule_days: List[int]
    tiers: List["LateFeeTierRead"]


class BillingPolicyUpdate(BaseModel):
    grace_period_days: conint(ge=0)
    dunning_schedule_days: List[conint(ge=0)]
    tiers: List["LateFeeTierUpdate"]


class LateFeeTierRead(BaseModel):
    id: int
    sequence_order: int
    trigger_days_after_grace: int
    fee_type: str
    fee_amount: Decimal
    fee_percent: float
    description: Optional[str]

    class Config:
        orm_mode = True


class LateFeeTierUpdate(BaseModel):
    id: Optional[int]
    sequence_order: conint(ge=1)
    trigger_days_after_grace: conint(ge=0)
    fee_type: Literal["flat", "percent"]
    fee_amount: condecimal(ge=0, max_digits=10, decimal_places=2) = Decimal("0")
    fee_percent: confloat(ge=0, le=100) = 0
    description: Optional[str]


class PaymentRead(BaseModel):
    id: int
    owner_id: int
    invoice_id: Optional[int]
    amount: Decimal
    date_received: datetime
    method: Optional[str]
    reference: Optional[str]
    notes: Optional[str]

    class Config:
        orm_mode = True


class LedgerEntryRead(BaseModel):
    id: int
    owner_id: int
    entry_type: str
    amount: Decimal
    balance_after: Optional[Decimal]
    description: Optional[str]
    timestamp: datetime

    class Config:
        orm_mode = True


class ContractCreate(BaseModel):
    vendor_name: str
    service_type: Optional[str]
    start_date: date
    end_date: Optional[date]
    auto_renew: bool = False
    termination_notice_deadline: Optional[date]
    file_path: Optional[str]
    value: Optional[Decimal]
    notes: Optional[str]


class ContractUpdate(BaseModel):
    service_type: Optional[str]
    end_date: Optional[date]
    auto_renew: Optional[bool]
    termination_notice_deadline: Optional[date]
    file_path: Optional[str]
    value: Optional[Decimal]
    notes: Optional[str]


class ContractRead(BaseModel):
    id: int
    vendor_name: str
    service_type: Optional[str]
    start_date: date
    end_date: Optional[date]
    auto_renew: bool
    termination_notice_deadline: Optional[date]
    file_path: Optional[str]
    value: Optional[Decimal]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class AnnouncementCreate(BaseModel):
    subject: str
    body: str
    delivery_methods: List[str] = ["email"]


class AnnouncementRead(BaseModel):
    id: int
    subject: str
    body: str
    created_at: datetime
    created_by_user_id: int
    delivery_methods: List[str]
    pdf_path: Optional[str]

    class Config:
        orm_mode = True


class EmailBroadcastRecipient(BaseModel):
    owner_id: Optional[int]
    owner_name: Optional[str]
    lot: Optional[str]
    email: EmailStr
    contact_type: Optional[str]


class EmailBroadcastCreate(BaseModel):
    subject: str
    body: str
    segment: Literal["ALL_OWNERS", "DELINQUENT_OWNERS", "RENTAL_OWNERS"]


class EmailBroadcastRead(BaseModel):
    id: int
    subject: str
    body: str
    segment: str
    recipients: List[EmailBroadcastRecipient] = Field(alias="recipient_snapshot")
    recipient_count: int
    created_at: datetime
    created_by_user_id: int

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class EmailBroadcastSegmentPreview(BaseModel):
    key: str
    label: str
    description: str
    recipient_count: int


class ReminderRead(BaseModel):
    id: int
    reminder_type: str
    title: str
    description: Optional[str]
    entity_type: str
    entity_id: int
    due_date: Optional[date]
    context: Optional[Dict[str, Any]]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        orm_mode = True


class OwnerExport(BaseModel):
    owner: OwnerRead
    invoices: List[InvoiceRead]
    payments: List[PaymentRead]
    ledger_entries: List[LedgerEntryRead]
    update_requests: List[OwnerUpdateRequestRead]


class AuditLogRead(BaseModel):
    id: int
    timestamp: datetime
    actor_user_id: Optional[int]
    action: str
    target_entity_type: Optional[str]
    target_entity_id: Optional[str]
    before: Optional[str]
    after: Optional[str]

    class Config:
        orm_mode = True


class BillingSummaryRead(BaseModel):
    total_balance: Decimal
    open_invoices: int
    owner_count: int


BillingPolicyRead.update_forward_refs()
BillingPolicyUpdate.update_forward_refs()
