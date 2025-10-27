from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


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
    due_date: date
    status: str
    late_fee_applied: bool
    notes: Optional[str]
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
