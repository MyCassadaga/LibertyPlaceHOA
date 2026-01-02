from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, confloat, condecimal, conint, root_validator


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
    role_ids: List[int] = Field(min_items=1)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    role: Optional[RoleRead]
    primary_role: Optional[RoleRead]
    roles: List[RoleRead] = []
    created_at: datetime
    is_active: bool
    archived_at: Optional[datetime]
    archived_reason: Optional[str]
    two_factor_enabled: bool = False

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    roles: List[str]
    primary_role: Optional[str]
    expires_in: int
    refresh_expires_in: int


class TokenPayload(BaseModel):
    sub: str
    roles: List[str]
    primary_role: Optional[str]
    exp: int
    type: str


class UserSelfUpdate(BaseModel):
    full_name: Optional[str]
    email: Optional[EmailStr]
    current_password: Optional[str] = Field(default=None, min_length=8)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class UserRoleUpdate(BaseModel):
    role_ids: List[int] = Field(min_items=1)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorVerifyRequest(BaseModel):
    otp: str = Field(min_length=6, max_length=6)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class NotificationRead(BaseModel):
    id: int
    title: str
    message: str
    level: str
    category: Optional[str]
    link_url: Optional[str]
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        orm_mode = True


class NotificationBroadcast(BaseModel):
    title: str
    message: str
    level: Optional[str] = "info"
    category: Optional[str]
    link_url: Optional[str]
    user_ids: Optional[List[int]]
    roles: Optional[List[str]]


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
    is_archived: bool
    archived_at: Optional[datetime]
    archived_reason: Optional[str]
    archived_by_user_id: Optional[int]
    former_lot: Optional[str]
    delivery_preference_global: str = "AUTO"
    linked_users: List[UserRead] = []

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


class OwnerSelfUpdate(BaseModel):
    primary_name: Optional[str]
    secondary_name: Optional[str]
    property_address: Optional[str]
    mailing_address: Optional[str]
    primary_email: Optional[EmailStr]
    secondary_email: Optional[EmailStr]
    primary_phone: Optional[str]
    secondary_phone: Optional[str]
    emergency_contact: Optional[str]
    notes: Optional[str]


class OwnerArchiveRequest(BaseModel):
    reason: Optional[str]


class OwnerRestoreRequest(BaseModel):
    reactivate_user: bool = False


class OwnerLinkRequest(BaseModel):
    user_id: int
    link_type: Optional[str]


class ElectionCandidateCreate(BaseModel):
    display_name: str
    statement: Optional[str]
    owner_id: Optional[int]


class ElectionCandidateRead(ElectionCandidateCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ElectionCreate(BaseModel):
    title: str
    description: Optional[str]
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    status: Optional[str] = "DRAFT"


class ElectionUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    status: Optional[str]


class ElectionResultRead(BaseModel):
    candidate_id: Optional[int]
    candidate_name: Optional[str]
    vote_count: int


class ElectionStatsRead(BaseModel):
    election_id: int
    ballot_count: int
    votes_cast: int
    turnout_percent: float
    abstentions: int
    write_in_count: int
    results: List[ElectionResultRead] = []


class ElectionRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    candidates: List[ElectionCandidateRead] = []
    ballot_count: int
    votes_cast: int
    results: List[ElectionResultRead] = []
    my_status: Optional["ElectionMyStatus"] = None

    class Config:
        orm_mode = True


class ElectionListItem(BaseModel):
    id: int
    title: str
    status: str
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    ballot_count: int
    votes_cast: int


class ElectionAdminBallotRead(BaseModel):
    id: int
    owner_id: int
    owner_name: Optional[str]
    token: str
    issued_at: datetime
    voted_at: Optional[datetime]


class ElectionPublicRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    candidates: List[ElectionCandidateRead] = []
    has_voted: bool = False


class ElectionVoteCast(BaseModel):
    token: str
    candidate_id: Optional[int]
    write_in: Optional[str]


class ElectionMyStatus(BaseModel):
    has_ballot: bool
    has_voted: bool
    voted_at: Optional[datetime]


class ElectionAuthenticatedVote(BaseModel):
    candidate_id: Optional[int]
    write_in: Optional[str]


class BudgetLineItemBase(BaseModel):
    label: str
    category: Optional[str]
    amount: Decimal
    is_reserve: bool = False
    sort_order: Optional[int]


class BudgetLineItemCreate(BudgetLineItemBase):
    pass


class BudgetLineItemUpdate(BaseModel):
    label: Optional[str]
    category: Optional[str]
    amount: Optional[Decimal]
    is_reserve: Optional[bool]
    sort_order: Optional[int]


class BudgetLineItemRead(BudgetLineItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ReservePlanItemBase(BaseModel):
    name: str
    target_year: int
    estimated_cost: Decimal
    inflation_rate: float = 0.0
    current_funding: Decimal = Decimal("0")
    notes: Optional[str]


class ReservePlanItemCreate(ReservePlanItemBase):
    pass


class ReservePlanItemUpdate(BaseModel):
    name: Optional[str]
    target_year: Optional[int]
    estimated_cost: Optional[Decimal]
    inflation_rate: Optional[float]
    current_funding: Optional[Decimal]
    notes: Optional[str]


class ReservePlanItemRead(ReservePlanItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class BudgetAttachmentRead(BaseModel):
    id: int
    file_name: str
    stored_path: str
    content_type: Optional[str]
    file_size: Optional[int]
    uploaded_at: datetime

    class Config:
        orm_mode = True


class BudgetAttachmentCreateResponse(BudgetAttachmentRead):
    pass


class BudgetApprovalRead(BaseModel):
    user_id: int
    full_name: Optional[str]
    email: Optional[str]
    approved_at: datetime

    class Config:
        orm_mode = True


class BudgetRead(BaseModel):
    id: int
    year: int
    status: str
    home_count: int
    notes: Optional[str]
    locked_at: Optional[datetime]
    locked_by_user_id: Optional[int]
    total_annual: Decimal
    operations_total: Decimal
    reserves_total: Decimal
    assessment_per_quarter: Decimal
    created_at: datetime
    updated_at: datetime
    line_items: List[BudgetLineItemRead]
    reserve_items: List[ReservePlanItemRead]
    attachments: List[BudgetAttachmentRead]
    approvals: List[BudgetApprovalRead]
    approval_count: int
    required_approvals: int
    user_has_approved: bool

    class Config:
        orm_mode = True


class BudgetSummary(BaseModel):
    id: int
    year: int
    status: str
    total_annual: Decimal
    assessment_per_quarter: Decimal


class BudgetCreate(BaseModel):
    year: int
    home_count: Optional[int] = None
    notes: Optional[str]


class BudgetUpdate(BaseModel):
    home_count: Optional[int]
    notes: Optional[str]


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


class AutopayEnrollmentRequest(BaseModel):
    payment_day: conint(ge=1, le=28) = 1
    amount_type: Literal["STATEMENT_BALANCE", "FIXED"] = "STATEMENT_BALANCE"
    fixed_amount: Optional[condecimal(ge=0, max_digits=10, decimal_places=2)]
    owner_id: Optional[int]

    @root_validator
    def validate_fixed_amount(cls, values):
        amount_type = values.get("amount_type")
        fixed_amount = values.get("fixed_amount")
        if amount_type == "FIXED" and fixed_amount is None:
            raise ValueError("fixed_amount is required when amount_type is FIXED")
        return values


class AutopayEnrollmentRead(BaseModel):
    owner_id: int
    status: str
    payment_day: Optional[int]
    amount_type: Literal["STATEMENT_BALANCE", "FIXED"]
    fixed_amount: Optional[Decimal]
    funding_source_mask: Optional[str]
    provider: str
    provider_status: Optional[str]
    provider_setup_required: bool = True
    last_run_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

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


class VendorPaymentCreate(BaseModel):
    contract_id: Optional[int]
    vendor_name: Optional[str]
    amount: condecimal(ge=0, max_digits=12, decimal_places=2)
    memo: Optional[str]

    @root_validator
    def vendor_requirement(cls, values):
        if not values.get("vendor_name") and not values.get("contract_id"):
            raise ValueError("vendor_name is required when contract_id is not provided")
        return values


class VendorPaymentRead(BaseModel):
    id: int
    contract_id: Optional[int]
    vendor_name: str
    amount: Decimal
    memo: Optional[str]
    status: str
    provider: str
    provider_status: Optional[str]
    provider_reference: Optional[str]
    requested_at: datetime
    submitted_at: Optional[datetime]
    paid_at: Optional[datetime]

    class Config:
        orm_mode = True


class AnnouncementCreate(BaseModel):
    subject: str
    body: str
    delivery_methods: List[str] = ["email"]


class TemplateCreate(BaseModel):
    name: str
    type: str
    subject: str
    body: str
    is_archived: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str]
    type: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    is_archived: Optional[bool]


class TemplateRead(BaseModel):
    id: int
    name: str
    type: str
    subject: str
    body: str
    is_archived: bool
    created_by_user_id: Optional[int]
    updated_by_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TemplateMergeTag(BaseModel):
    key: str
    label: str
    description: str
    sample: str


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
    property_address: Optional[str]
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


class FineScheduleRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    base_amount: Decimal
    escalation_amount: Optional[Decimal]
    escalation_days: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ViolationNoticeRead(BaseModel):
    id: int
    violation_id: int
    notice_type: str
    template_key: str
    subject: str
    body: str
    pdf_path: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class AppealCreate(BaseModel):
    reason: str


class AppealDecision(BaseModel):
    status: Literal["APPROVED", "DENIED"]
    decision_notes: Optional[str]


class AppealRead(BaseModel):
    id: int
    violation_id: int
    submitted_by_owner_id: int
    status: str
    reason: str
    decision_notes: Optional[str]
    submitted_at: datetime
    decided_at: Optional[datetime]
    reviewed_by_user_id: Optional[int]

    class Config:
        orm_mode = True


class ViolationCreate(BaseModel):
    owner_id: Optional[int]
    user_id: Optional[int]
    category: str
    description: Optional[str]
    location: Optional[str]
    fine_schedule_id: Optional[int]
    due_date: Optional[date]

    @root_validator
    def ensure_owner_or_user(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        owner_id = values.get("owner_id")
        user_id = values.get("user_id")
        if not owner_id and not user_id:
            raise ValueError("Either owner_id or user_id must be provided.")
        return values


class ViolationUpdate(BaseModel):
    category: Optional[str]
    description: Optional[str]
    location: Optional[str]
    due_date: Optional[date]
    hearing_date: Optional[date]
    fine_amount: Optional[Decimal]
    resolution_notes: Optional[str]


class ViolationStatusUpdate(BaseModel):
    target_status: Literal[
        "NEW",
        "UNDER_REVIEW",
        "WARNING_SENT",
        "HEARING",
        "FINE_ACTIVE",
        "RESOLVED",
        "ARCHIVED",
    ]
    note: Optional[str]
    hearing_date: Optional[date]
    fine_amount: Optional[Decimal]
    template_id: Optional[int]


class ViolationAdditionalFine(BaseModel):
    amount: condecimal(gt=0)
    template_id: Optional[int]


class ViolationMessageCreate(BaseModel):
    body: str


class ViolationMessageRead(BaseModel):
    id: int
    violation_id: int
    user_id: Optional[int]
    body: str
    created_at: datetime
    author_name: Optional[str]
    author_email: Optional[str]


class ViolationRead(BaseModel):
    id: int
    owner_id: int
    reported_by_user_id: int
    fine_schedule_id: Optional[int]
    status: str
    category: str
    description: Optional[str]
    location: Optional[str]
    opened_at: datetime
    updated_at: datetime
    due_date: Optional[date]
    hearing_date: Optional[date]
    fine_amount: Optional[Decimal]
    resolution_notes: Optional[str]
    owner: OwnerRead
    notices: List[ViolationNoticeRead] = []
    appeals: List[AppealRead] = []
    messages: List[ViolationMessageRead] = []

    class Config:
        orm_mode = True


class ARCAttachmentRead(BaseModel):
    id: int
    arc_request_id: int
    original_filename: str
    stored_filename: str
    content_type: Optional[str]
    file_size: Optional[int]
    uploaded_at: datetime

    class Config:
        orm_mode = True


class ARCConditionCreate(BaseModel):
    text: str
    condition_type: Literal["COMMENT", "REQUIREMENT"] = "COMMENT"


class ARCConditionResolve(BaseModel):
    status: Literal["OPEN", "RESOLVED"]


class ARCConditionRead(BaseModel):
    id: int
    arc_request_id: int
    condition_type: str
    text: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    created_by_user_id: int

    class Config:
        orm_mode = True


class ARCInspectionCreate(BaseModel):
    scheduled_date: Optional[date]
    result: Optional[str]
    notes: Optional[str]


class ARCInspectionRead(BaseModel):
    id: int
    arc_request_id: int
    inspector_user_id: Optional[int]
    scheduled_date: Optional[date]
    completed_at: Optional[datetime]
    result: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class ARCRequestCreate(BaseModel):
    title: str
    project_type: Optional[str]
    description: Optional[str]
    owner_id: Optional[int]


class ARCRequestUpdate(BaseModel):
    title: Optional[str]
    project_type: Optional[str]
    description: Optional[str]


class ARCRequestStatusUpdate(BaseModel):
    target_status: Literal[
        "DRAFT",
        "SUBMITTED",
        "IN_REVIEW",
        "REVISION_REQUESTED",
        "APPROVED",
        "APPROVED_WITH_CONDITIONS",
        "DENIED",
        "COMPLETED",
        "ARCHIVED",
    ]
    reviewer_user_id: Optional[int]
    notes: Optional[str]


class ARCRequestRead(BaseModel):
    id: int
    owner_id: int
    submitted_by_user_id: int
    reviewer_user_id: Optional[int]
    title: str
    project_type: Optional[str]
    description: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    decision_notes: Optional[str]
    final_decision_at: Optional[datetime]
    final_decision_by_user_id: Optional[int]
    revision_requested_at: Optional[datetime]
    completed_at: Optional[datetime]
    archived_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    owner: OwnerRead
    attachments: List[ARCAttachmentRead]
    conditions: List[ARCConditionRead]
    inspections: List[ARCInspectionRead]

    class Config:
        orm_mode = True


class BankTransactionRead(BaseModel):
    id: int
    reconciliation_id: Optional[int]
    uploaded_by_user_id: int
    transaction_date: Optional[date]
    description: Optional[str]
    reference: Optional[str]
    amount: Decimal
    status: str
    matched_payment_id: Optional[int]
    matched_invoice_id: Optional[int]
    source_file: Optional[str]
    uploaded_at: datetime

    class Config:
        orm_mode = True


class ReconciliationRead(BaseModel):
    id: int
    statement_date: Optional[date]
    created_by_user_id: int
    note: Optional[str]
    total_transactions: int
    matched_transactions: int
    unmatched_transactions: int
    matched_amount: Decimal
    unmatched_amount: Decimal
    created_at: datetime
    transactions: List[BankTransactionRead] = []

    class Config:
        orm_mode = True


class BankImportSummary(BaseModel):
    reconciliation: ReconciliationRead


class OwnerExport(BaseModel):
    owner: OwnerRead
    invoices: List[InvoiceRead]
    payments: List[PaymentRead]
    ledger_entries: List[LedgerEntryRead]
    update_requests: List[OwnerUpdateRequestRead]


class ResidentRead(BaseModel):
    user: Optional[UserRead]
    owner: Optional[OwnerRead]

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


class OverdueInvoiceRead(BaseModel):
    id: int
    amount: Decimal
    due_date: date
    status: str
    days_overdue: int
    months_overdue: int
    reminders_sent: int


class OverdueAccountRead(BaseModel):
    owner_id: int
    owner_name: str
    property_address: Optional[str]
    primary_email: Optional[str]
    primary_phone: Optional[str]
    total_due: Decimal
    max_months_overdue: int
    last_reminder_sent_at: Optional[datetime]
    invoices: List[OverdueInvoiceRead]


class OverdueContactRequest(BaseModel):
    message: Optional[str]


class OverdueContactResponse(BaseModel):
    notified_user_ids: List[int]


class ForwardAttorneyRequest(BaseModel):
    notes: Optional[str]


class ForwardAttorneyResponse(BaseModel):
    notice_url: str


class NoticeCreateRequest(BaseModel):
    owner_id: int
    notice_type_code: str
    subject: str
    body_html: str


DeliveryMethod = Literal["STANDARD_MAIL", "CERTIFIED_MAIL"]


class PaperworkDispatchRequest(BaseModel):
    delivery_method: DeliveryMethod


class PaperworkItemRead(BaseModel):
    id: int
    notice_id: int
    owner_id: int
    required: bool
    status: str
    claimed_by_board_member_id: Optional[int]
    claimed_at: Optional[datetime]
    mailed_at: Optional[datetime]
    delivery_method: Optional[str]
    delivery_provider: Optional[str]
    provider_job_id: Optional[str]
    provider_status: Optional[str]
    tracking_number: Optional[str]
    delivery_status: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


class NoticeRead(BaseModel):
    id: int
    owner_id: int
    notice_type_id: int
    subject: str
    body_html: str
    delivery_channel: str
    status: str
    created_at: datetime
    sent_email_at: Optional[datetime]
    mailed_at: Optional[datetime]
    delivery_method: Optional[str]
    tracking_number: Optional[str]
    delivery_status: Optional[str]
    delivered_at: Optional[datetime]
    paperwork_item: Optional[PaperworkItemRead]

    class Config:
        orm_mode = True


class PaperworkListItem(BaseModel):
    id: int
    notice_id: int
    owner_id: int
    owner_name: str
    owner_address: str
    notice_type_code: str
    subject: str
    required: bool
    status: str
    delivery_method: Optional[str]
    delivery_provider: Optional[str]
    provider_status: Optional[str]
    provider_job_id: Optional[str]
    tracking_number: Optional[str]
    delivery_status: Optional[str]
    delivered_at: Optional[datetime]
    pdf_available: bool
    claimed_by: Optional[UserRead]
    claimed_at: Optional[datetime]
    mailed_at: Optional[datetime]
    created_at: datetime


BillingPolicyRead.update_forward_refs()
BillingPolicyUpdate.update_forward_refs()
ElectionRead.update_forward_refs()


class GovernanceDocumentRead(BaseModel):
    id: int
    folder_id: Optional[int]
    title: str
    description: Optional[str]
    content_type: Optional[str]
    file_size: Optional[int]
    uploaded_by_user_id: Optional[int]
    created_at: datetime
    download_url: str

    class Config:
        orm_mode = True


class DocumentFolderRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    documents: List[GovernanceDocumentRead] = []
    children: List["DocumentFolderRead"] = []

    class Config:
        orm_mode = True


DocumentFolderRead.update_forward_refs()


class DocumentFolderCreate(BaseModel):
    name: str
    description: Optional[str]
    parent_id: Optional[int]


class DocumentFolderUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    parent_id: Optional[int]


class DocumentUploadResponse(BaseModel):
    document: GovernanceDocumentRead


class DocumentTreeResponse(BaseModel):
    folders: List[DocumentFolderRead]
    root_documents: List[GovernanceDocumentRead]


class MeetingRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    location: Optional[str]
    zoom_link: Optional[str]
    minutes_available: bool
    minutes_download_url: Optional[str]
    created_by_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class MeetingCreate(BaseModel):
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    location: Optional[str]
    zoom_link: Optional[str]


class MeetingUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    location: Optional[str]
    zoom_link: Optional[str]


class AuditLogActor(BaseModel):
    id: Optional[int]
    email: Optional[str]
    full_name: Optional[str]


class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    action: str
    target_entity_type: Optional[str]
    target_entity_id: Optional[str]
    before: Optional[str]
    after: Optional[str]
    actor: AuditLogActor

    class Config:
        orm_mode = True


class AuditLogList(BaseModel):
    items: List[AuditLogEntry]
    total: int
