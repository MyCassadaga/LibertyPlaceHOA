from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship as orm_relationship

from ..config import Base
from ..constants import ROLE_PRIORITY


def utcnow():
    return datetime.now(timezone.utc)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=utcnow, nullable=False),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    users = orm_relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        overlaps="primary_role,primary_users",
    )
    permissions = orm_relationship("Permission", secondary=role_permissions, back_populates="roles")
    primary_users = orm_relationship(
        "User",
        back_populates="primary_role",
        foreign_keys="User.role_id",
        overlaps="users,roles",
    )


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    roles = orm_relationship("Role", secondary=role_permissions, back_populates="permissions")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_reason = Column(Text, nullable=True)
    two_factor_secret = Column(String, nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)

    primary_role = orm_relationship(
        "Role",
        back_populates="primary_users",
        foreign_keys=[role_id],
        overlaps="users,roles",
    )
    roles = orm_relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        overlaps="primary_role,primary_users",
    )
    audit_logs = orm_relationship("AuditLog", back_populates="actor")
    email_broadcasts = orm_relationship("EmailBroadcast", back_populates="creator")
    owner_links = orm_relationship("OwnerUserLink", back_populates="user", cascade="all, delete-orphan")
    owners = orm_relationship("Owner", secondary="owner_user_links", viewonly=True)
    created_elections = orm_relationship("Election", back_populates="created_by")
    notifications = orm_relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    @property
    def role(self):
        if self.primary_role:
            return self.primary_role
        if self.roles:
            return max(self.roles, key=lambda role: ROLE_PRIORITY.get(role.name, 0))
        return None

    @role.setter
    def role(self, value):
        self.primary_role = value

    @property
    def role_names(self) -> list[str]:
        return [role.name for role in self.roles] if self.roles else ([self.primary_role.name] if self.primary_role else [])

    def has_role(self, role_name: str) -> bool:
        if any(role.name == role_name for role in self.roles):
            return True
        return self.primary_role.name == role_name if self.primary_role else False

    def has_any_role(self, *role_names: str) -> bool:
        targets = set(role_names)
        if not targets:
            return False
        return any(role.name in targets for role in self.roles) or (
            self.primary_role.name in targets if self.primary_role else False
        )

    @property
    def highest_priority_role(self):
        if self.roles:
            return max(self.roles, key=lambda role: ROLE_PRIORITY.get(role.name, 0))
        return self.primary_role


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    target_entity_type = Column(String, nullable=True)
    target_entity_id = Column(String, nullable=True)
    before = Column(Text, nullable=True)
    after = Column(Text, nullable=True)

    actor = orm_relationship("User", back_populates="audit_logs")


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    primary_name = Column(String, nullable=False)
    secondary_name = Column(String, nullable=True)
    lot = Column(String, nullable=False, unique=True)
    property_address = Column(String, nullable=False)
    mailing_address = Column(String, nullable=True)
    primary_email = Column(String, nullable=True)
    secondary_email = Column(String, nullable=True)
    primary_phone = Column(String, nullable=True)
    secondary_phone = Column(String, nullable=True)
    occupancy_status = Column(String, default="OWNER_OCCUPIED")
    emergency_contact = Column(String, nullable=True)
    is_rental = Column(Boolean, default=False)
    lease_document_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    archived_reason = Column(Text, nullable=True)
    former_lot = Column(String, nullable=True)
    delivery_preference_global = Column(String, nullable=False, default="AUTO", index=True)

    invoices = orm_relationship("Invoice", back_populates="owner", cascade="all, delete-orphan")
    payments = orm_relationship("Payment", back_populates="owner", cascade="all, delete-orphan")
    ledger_entries = orm_relationship("LedgerEntry", back_populates="owner", cascade="all, delete-orphan")
    update_requests = orm_relationship("OwnerUpdateRequest", back_populates="owner", cascade="all, delete-orphan")
    archived_by = orm_relationship("User", foreign_keys=[archived_by_user_id])
    user_links = orm_relationship("OwnerUserLink", back_populates="owner", cascade="all, delete-orphan")
    linked_users = orm_relationship("User", secondary="owner_user_links", viewonly=True)
    election_ballots = orm_relationship("ElectionBallot", back_populates="owner", cascade="all, delete-orphan")
    notices = orm_relationship("Notice", back_populates="owner", cascade="all, delete-orphan")
    autopay_enrollment = orm_relationship("AutopayEnrollment", back_populates="owner", uselist=False)


class OwnerUserLink(Base):
    __tablename__ = "owner_user_links"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="user_links")
    user = orm_relationship("User", back_populates="owner_links")


class OwnerUpdateRequest(Base):
    __tablename__ = "owner_update_requests"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    proposed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    proposed_changes = Column(JSON, nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    owner = orm_relationship("Owner", back_populates="update_requests")
    proposer = orm_relationship("User", foreign_keys=[proposed_by_user_id])
    reviewer = orm_relationship("User", foreign_keys=[reviewer_user_id])


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    lot = Column(String, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    original_amount = Column(Numeric(10, 2), nullable=False)
    late_fee_total = Column(Numeric(10, 2), nullable=False, default=0)
    due_date = Column(Date, nullable=False)
    status = Column(String, default="OPEN", nullable=False)
    late_fee_applied = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    last_late_fee_applied_at = Column(DateTime, nullable=True)
    last_reminder_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="invoices")
    payments = orm_relationship("Payment", back_populates="invoice")
    late_fees = orm_relationship("InvoiceLateFee", back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    date_received = Column(DateTime, default=utcnow, nullable=False)
    method = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    owner = orm_relationship("Owner", back_populates="payments")
    invoice = orm_relationship("Invoice", back_populates="payments")


class AutopayEnrollment(Base):
    __tablename__ = "autopay_enrollments"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_autopay_owner"),)

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    payment_day = Column(Integer, nullable=False, default=1)
    amount_type = Column(String, nullable=False, default="STATEMENT_BALANCE")
    fixed_amount = Column(Numeric(10, 2), nullable=True)
    funding_source_type = Column(String, nullable=True)
    funding_source_mask = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_payment_method_id = Column(String, nullable=True)
    provider_status = Column(String, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="autopay_enrollment")
    user = orm_relationship("User")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    entry_type = Column(String, nullable=False)  # invoice|payment|adjustment
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=True)
    description = Column(String, nullable=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="ledger_entries")


class BillingPolicy(Base):
    __tablename__ = "billing_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    grace_period_days = Column(Integer, nullable=False, default=5)
    dunning_schedule_days = Column(JSON, nullable=False, default=[5, 15, 30])
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    tiers = orm_relationship("LateFeeTier", back_populates="policy", cascade="all, delete-orphan", order_by="LateFeeTier.sequence_order")


class LateFeeTier(Base):
    __tablename__ = "late_fee_tiers"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("billing_policies.id", ondelete="CASCADE"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    trigger_days_after_grace = Column(Integer, nullable=False)
    fee_type = Column(String, nullable=False, default="flat")  # flat|percent
    fee_amount = Column(Numeric(10, 2), nullable=False, default=0)
    fee_percent = Column(Float, nullable=False, default=0)  # stored as percentage e.g. 5 = 5%
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    policy = orm_relationship("BillingPolicy", back_populates="tiers")
    invoice_fees = orm_relationship("InvoiceLateFee", back_populates="tier")


class InvoiceLateFee(Base):
    __tablename__ = "invoice_late_fees"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    tier_id = Column(Integer, ForeignKey("late_fee_tiers.id", ondelete="CASCADE"), nullable=False)
    applied_at = Column(DateTime, default=utcnow, nullable=False)
    fee_amount = Column(Numeric(10, 2), nullable=False)

    invoice = orm_relationship("Invoice", back_populates="late_fees")
    tier = orm_relationship("LateFeeTier", back_populates="invoice_fees")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    vendor_name = Column(String, nullable=False)
    service_type = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    auto_renew = Column(Boolean, default=False, nullable=False)
    termination_notice_deadline = Column(Date, nullable=True)
    file_path = Column(String, nullable=True)
    value = Column(Numeric(12, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    vendor_payments = orm_relationship("VendorPayment", back_populates="contract", cascade="all, delete-orphan")


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delivery_methods = Column(JSON, nullable=False, default=["email"])
    pdf_path = Column(String, nullable=True)

    creator = orm_relationship("User", foreign_keys=[created_by_user_id])


class EmailBroadcast(Base):
    __tablename__ = "email_broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    segment = Column(String, nullable=False)
    recipient_snapshot = Column(JSON, nullable=False, default=list)
    recipient_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    creator = orm_relationship("User", back_populates="email_broadcasts")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    reminder_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=True)
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class FineSchedule(Base):
    __tablename__ = "fine_schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    base_amount = Column(Numeric(10, 2), nullable=False, default=0)
    escalation_amount = Column(Numeric(10, 2), nullable=True)
    escalation_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    violations = orm_relationship("Violation", back_populates="fine_schedule")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    reported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fine_schedule_id = Column(Integer, ForeignKey("fine_schedules.id"), nullable=True)
    status = Column(String, nullable=False, index=True, default="NEW")
    category = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    opened_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    due_date = Column(Date, nullable=True)
    hearing_date = Column(Date, nullable=True)
    fine_amount = Column(Numeric(10, 2), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    owner = orm_relationship("Owner", backref="violations")
    reporter = orm_relationship("User", foreign_keys=[reported_by_user_id])
    fine_schedule = orm_relationship("FineSchedule", back_populates="violations")
    notices = orm_relationship("ViolationNotice", back_populates="violation", cascade="all, delete-orphan")
    appeals = orm_relationship("Appeal", back_populates="violation", cascade="all, delete-orphan")
    messages = orm_relationship("ViolationMessage", back_populates="violation", cascade="all, delete-orphan")


class VendorPayment(Base):
    __tablename__ = "vendor_payments"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True)
    vendor_name = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    memo = Column(Text, nullable=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    provider = Column(String, nullable=False, default="STRIPE")
    provider_status = Column(String, nullable=True)
    provider_reference = Column(String, nullable=True)
    requested_at = Column(DateTime, default=utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    contract = orm_relationship("Contract", back_populates="vendor_payments")
    requested_by = orm_relationship("User", foreign_keys=[requested_by_user_id])


class ViolationNotice(Base):
    __tablename__ = "violation_notices"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id", ondelete="CASCADE"), nullable=False)
    sent_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notice_type = Column(String, nullable=False)  # EMAIL | POSTAL
    template_key = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    pdf_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    violation = orm_relationship("Violation", back_populates="notices")
    sender = orm_relationship("User", foreign_keys=[sent_by_user_id])


class ViolationMessage(Base):
    __tablename__ = "violation_messages"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    violation = orm_relationship("Violation", back_populates="messages")
    author = orm_relationship("User")


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id", ondelete="CASCADE"), nullable=False)
    submitted_by_owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    reason = Column(Text, nullable=False)
    decision_notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    violation = orm_relationship("Violation", back_populates="appeals")
    submitted_by = orm_relationship("Owner", foreign_keys=[submitted_by_owner_id])
    reviewer = orm_relationship("User", foreign_keys=[reviewed_by_user_id])


class ARCRequest(Base):
    __tablename__ = "arc_requests"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String, nullable=False)
    project_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    submitted_at = Column(DateTime, nullable=True)
    decision_notes = Column(Text, nullable=True)
    final_decision_at = Column(DateTime, nullable=True)
    final_decision_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    revision_requested_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = orm_relationship("Owner", backref="arc_requests")
    applicant = orm_relationship("User", foreign_keys=[submitted_by_user_id])
    reviewer = orm_relationship("User", foreign_keys=[reviewer_user_id], post_update=True)
    final_decision_by = orm_relationship("User", foreign_keys=[final_decision_by_user_id], post_update=True)
    attachments = orm_relationship("ARCAttachment", back_populates="request", cascade="all, delete-orphan")
    conditions = orm_relationship("ARCCondition", back_populates="request", cascade="all, delete-orphan")
    inspections = orm_relationship("ARCInspection", back_populates="request", cascade="all, delete-orphan")


class ARCAttachment(Base):
    __tablename__ = "arc_attachments"

    id = Column(Integer, primary_key=True, index=True)
    arc_request_id = Column(Integer, ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=utcnow, nullable=False)

    request = orm_relationship("ARCRequest", back_populates="attachments")
    uploader = orm_relationship("User")


class ARCCondition(Base):
    __tablename__ = "arc_conditions"

    id = Column(Integer, primary_key=True, index=True)
    arc_request_id = Column(Integer, ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    condition_type = Column(String, nullable=False, default="COMMENT")  # COMMENT | REQUIREMENT
    text = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="OPEN")  # OPEN | RESOLVED
    created_at = Column(DateTime, default=utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    request = orm_relationship("ARCRequest", back_populates="conditions")
    author = orm_relationship("User")


class ARCInspection(Base):
    __tablename__ = "arc_inspections"

    id = Column(Integer, primary_key=True, index=True)
    arc_request_id = Column(Integer, ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False)
    inspector_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheduled_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(String, nullable=True)  # PASSED | FAILED | N/A
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    request = orm_relationship("ARCRequest", back_populates="inspections")
    inspector = orm_relationship("User")


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(Date, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    total_transactions = Column(Integer, nullable=False, default=0)
    matched_transactions = Column(Integer, nullable=False, default=0)
    unmatched_transactions = Column(Integer, nullable=False, default=0)
    matched_amount = Column(Numeric(12, 2), nullable=False, default=0)
    unmatched_amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    creator = orm_relationship("User")
    transactions = orm_relationship("BankTransaction", back_populates="reconciliation", cascade="all, delete-orphan")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_id = Column(Integer, ForeignKey("reconciliations.id", ondelete="CASCADE"), nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # MATCHED | UNMATCHED | PENDING
    matched_payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    matched_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    source_file = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=utcnow, nullable=False)

    reconciliation = orm_relationship("Reconciliation", back_populates="transactions")
    uploader = orm_relationship("User")


class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="DRAFT", nullable=False)
    opens_at = Column(DateTime, nullable=True)
    closes_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    candidates = orm_relationship("ElectionCandidate", back_populates="election", cascade="all, delete-orphan")
    ballots = orm_relationship("ElectionBallot", back_populates="election", cascade="all, delete-orphan")
    votes = orm_relationship("ElectionVote", back_populates="election", cascade="all, delete-orphan")
    created_by = orm_relationship("User", back_populates="created_elections", foreign_keys=[created_by_user_id])


class ElectionCandidate(Base):
    __tablename__ = "election_candidates"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True)
    display_name = Column(String, nullable=False)
    statement = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    election = orm_relationship("Election", back_populates="candidates")
    owner = orm_relationship("Owner")
    votes = orm_relationship("ElectionVote", back_populates="candidate")


class ElectionBallot(Base):
    __tablename__ = "election_ballots"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    issued_at = Column(DateTime, default=utcnow, nullable=False)
    voted_at = Column(DateTime, nullable=True)
    invalidated_at = Column(DateTime, nullable=True)

    election = orm_relationship("Election", back_populates="ballots")
    owner = orm_relationship("Owner", back_populates="election_ballots")
    vote = orm_relationship("ElectionVote", uselist=False, back_populates="ballot")


class ElectionVote(Base):
    __tablename__ = "election_votes"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("election_candidates.id", ondelete="SET NULL"), nullable=True)
    ballot_id = Column(Integer, ForeignKey("election_ballots.id", ondelete="CASCADE"), nullable=False)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    write_in = Column(String, nullable=True)

    election = orm_relationship("Election", back_populates="votes")
    candidate = orm_relationship("ElectionCandidate", back_populates="votes")
    ballot = orm_relationship("ElectionBallot", back_populates="vote")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String, default="info", nullable=False)
    category = Column(String, nullable=True)
    link_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)

    user = orm_relationship("User", back_populates="notifications")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="DRAFT")
    home_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    locked_by = orm_relationship("User")
    line_items = orm_relationship("BudgetLineItem", back_populates="budget", cascade="all, delete-orphan")
    reserve_items = orm_relationship("ReservePlanItem", back_populates="budget", cascade="all, delete-orphan")
    attachments = orm_relationship("BudgetAttachment", back_populates="budget", cascade="all, delete-orphan")
    approvals = orm_relationship("BudgetApproval", back_populates="budget", cascade="all, delete-orphan")


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String, nullable=False)
    category = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    is_reserve = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    budget = orm_relationship("Budget", back_populates="line_items")


class ReservePlanItem(Base):
    __tablename__ = "reserve_plan_items"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    target_year = Column(Integer, nullable=False)
    estimated_cost = Column(Numeric(14, 2), nullable=False)
    inflation_rate = Column(Float, nullable=False, default=0.0)
    current_funding = Column(Numeric(14, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    budget = orm_relationship("Budget", back_populates="reserve_items")


class BudgetAttachment(Base):
    __tablename__ = "budget_attachments"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=utcnow, nullable=False)

    budget = orm_relationship("Budget", back_populates="attachments")


class BudgetApproval(Base):
    __tablename__ = "budget_approvals"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    approved_at = Column(DateTime, default=utcnow, nullable=False)

    budget = orm_relationship("Budget", back_populates="approvals")
    user = orm_relationship("User")


class NoticeType(Base):
    __tablename__ = "notice_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    allow_electronic = Column(Boolean, nullable=False, default=True)
    requires_paper = Column(Boolean, nullable=False, default=False)
    default_delivery = Column(String, nullable=False, default="AUTO")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    notices = orm_relationship("Notice", back_populates="notice_type")


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    notice_type_id = Column(Integer, ForeignKey("notice_types.id", ondelete="RESTRICT"), nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)
    delivery_channel = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    sent_email_at = Column(DateTime, nullable=True)
    mailed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    owner = orm_relationship("Owner", back_populates="notices")
    notice_type = orm_relationship("NoticeType", back_populates="notices")
    creator = orm_relationship("User")
    paperwork_item = orm_relationship("PaperworkItem", back_populates="notice", uselist=False, cascade="all, delete-orphan")


class PaperworkItem(Base):
    __tablename__ = "paperwork_items"

    id = Column(Integer, primary_key=True, index=True)
    notice_id = Column(Integer, ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    required = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="PENDING")
    claimed_by_board_member_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    mailed_at = Column(DateTime, nullable=True)
    delivery_provider = Column(String, nullable=True)
    provider_job_id = Column(String, nullable=True)
    provider_status = Column(String, nullable=True)
    provider_meta = Column(JSON, nullable=True)
    pdf_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    notice = orm_relationship("Notice", back_populates="paperwork_item")
    owner = orm_relationship("Owner")
    claimed_by = orm_relationship("User")


class DocumentFolder(Base):
    __tablename__ = "document_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("document_folders.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    parent = orm_relationship("DocumentFolder", remote_side=[id], backref="children")
    created_by = orm_relationship("User")
    documents = orm_relationship("GovernanceDocument", back_populates="folder")


class GovernanceDocument(Base):
    __tablename__ = "governance_documents"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("document_folders.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    folder = orm_relationship("DocumentFolder", back_populates="documents")
    uploaded_by = orm_relationship("User")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    location = Column(String, nullable=True)
    zoom_link = Column(String, nullable=True)
    minutes_file_path = Column(String, nullable=True)
    minutes_content_type = Column(String, nullable=True)
    minutes_file_size = Column(Integer, nullable=True)
    minutes_uploaded_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    created_by = orm_relationship("User")
