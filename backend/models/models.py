from datetime import datetime
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
)
from sqlalchemy.orm import relationship as orm_relationship

from ..config import Base
from ..constants import ROLE_PRIORITY


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
    Column("assigned_at", DateTime, default=datetime.utcnow, nullable=False),
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
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
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    archived_reason = Column(Text, nullable=True)
    former_lot = Column(String, nullable=True)

    invoices = orm_relationship("Invoice", back_populates="owner", cascade="all, delete-orphan")
    payments = orm_relationship("Payment", back_populates="owner", cascade="all, delete-orphan")
    ledger_entries = orm_relationship("LedgerEntry", back_populates="owner", cascade="all, delete-orphan")
    update_requests = orm_relationship("OwnerUpdateRequest", back_populates="owner", cascade="all, delete-orphan")
    archived_by = orm_relationship("User", foreign_keys=[archived_by_user_id])
    user_links = orm_relationship("OwnerUserLink", back_populates="owner", cascade="all, delete-orphan")
    linked_users = orm_relationship("User", secondary="owner_user_links", viewonly=True)


class OwnerUserLink(Base):
    __tablename__ = "owner_user_links"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="invoices")
    payments = orm_relationship("Payment", back_populates="invoice")
    late_fees = orm_relationship("InvoiceLateFee", back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    date_received = Column(DateTime, default=datetime.utcnow, nullable=False)
    method = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    owner = orm_relationship("Owner", back_populates="payments")
    invoice = orm_relationship("Invoice", back_populates="payments")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    entry_type = Column(String, nullable=False)  # invoice|payment|adjustment
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=True)
    description = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = orm_relationship("Owner", back_populates="ledger_entries")


class BillingPolicy(Base):
    __tablename__ = "billing_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    grace_period_days = Column(Integer, nullable=False, default=5)
    dunning_schedule_days = Column(JSON, nullable=False, default=[5, 15, 30])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    policy = orm_relationship("BillingPolicy", back_populates="tiers")
    invoice_fees = orm_relationship("InvoiceLateFee", back_populates="tier")


class InvoiceLateFee(Base):
    __tablename__ = "invoice_late_fees"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    tier_id = Column(Integer, ForeignKey("late_fee_tiers.id", ondelete="CASCADE"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class FineSchedule(Base):
    __tablename__ = "fine_schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    base_amount = Column(Numeric(10, 2), nullable=False, default=0)
    escalation_amount = Column(Numeric(10, 2), nullable=True)
    escalation_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    due_date = Column(Date, nullable=True)
    hearing_date = Column(Date, nullable=True)
    fine_amount = Column(Numeric(10, 2), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    owner = orm_relationship("Owner", backref="violations")
    reporter = orm_relationship("User", foreign_keys=[reported_by_user_id])
    fine_schedule = orm_relationship("FineSchedule", back_populates="violations")
    notices = orm_relationship("ViolationNotice", back_populates="violation", cascade="all, delete-orphan")
    appeals = orm_relationship("Appeal", back_populates="violation", cascade="all, delete-orphan")


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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    violation = orm_relationship("Violation", back_populates="notices")
    sender = orm_relationship("User", foreign_keys=[sent_by_user_id])


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id", ondelete="CASCADE"), nullable=False)
    submitted_by_owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    reason = Column(Text, nullable=False)
    decision_notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reconciliation = orm_relationship("Reconciliation", back_populates="transactions")
    uploader = orm_relationship("User")
