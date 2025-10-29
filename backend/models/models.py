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
from sqlalchemy.orm import relationship

from ..config import Base


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    role = relationship("Role", back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="actor")
    email_broadcasts = relationship("EmailBroadcast", back_populates="creator")


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

    actor = relationship("User", back_populates="audit_logs")


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

    invoices = relationship("Invoice", back_populates="owner", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="owner", cascade="all, delete-orphan")
    ledger_entries = relationship("LedgerEntry", back_populates="owner", cascade="all, delete-orphan")
    update_requests = relationship("OwnerUpdateRequest", back_populates="owner", cascade="all, delete-orphan")


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

    owner = relationship("Owner", back_populates="update_requests")
    proposer = relationship("User", foreign_keys=[proposed_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])


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

    owner = relationship("Owner", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    late_fees = relationship("InvoiceLateFee", back_populates="invoice", cascade="all, delete-orphan")


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

    owner = relationship("Owner", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    entry_type = Column(String, nullable=False)  # invoice|payment|adjustment
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=True)
    description = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="ledger_entries")


class BillingPolicy(Base):
    __tablename__ = "billing_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    grace_period_days = Column(Integer, nullable=False, default=5)
    dunning_schedule_days = Column(JSON, nullable=False, default=[5, 15, 30])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tiers = relationship("LateFeeTier", back_populates="policy", cascade="all, delete-orphan", order_by="LateFeeTier.sequence_order")


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

    policy = relationship("BillingPolicy", back_populates="tiers")
    invoice_fees = relationship("InvoiceLateFee", back_populates="tier")


class InvoiceLateFee(Base):
    __tablename__ = "invoice_late_fees"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    tier_id = Column(Integer, ForeignKey("late_fee_tiers.id", ondelete="CASCADE"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fee_amount = Column(Numeric(10, 2), nullable=False)

    invoice = relationship("Invoice", back_populates="late_fees")
    tier = relationship("LateFeeTier", back_populates="invoice_fees")


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

    creator = relationship("User", foreign_keys=[created_by_user_id])


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

    creator = relationship("User", back_populates="email_broadcasts")


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
