"""Phase 2 additions: violations and ARC workflow tables.

Revision ID: 0004_phase2_arc_violations
Revises: 0004_contract_reminders
Create Date: 2024-11-01
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op


revision = "0004_phase2_arc_violations"
down_revision = "0004_contract_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def ensure_index(table_name: str, index_name: str, columns: list[str], created: bool = False) -> None:
        if created:
            op.create_index(index_name, table_name, columns, unique=False)
            return
        try:
            existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
        except sa.exc.NoSuchTableError:
            existing = set()
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, unique=False)

    created_fine_schedules = False
    if not inspector.has_table("fine_schedules"):
        op.create_table(
            "fine_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("base_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("escalation_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("escalation_days", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_fine_schedules = True
    ensure_index("fine_schedules", "ix_fine_schedules_id", ["id"], created=created_fine_schedules)

    created_violations = False
    if not inspector.has_table("violations"):
        op.create_table(
            "violations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("fine_schedule_id", sa.Integer(), sa.ForeignKey("fine_schedules.id"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="NEW"),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("location", sa.String(), nullable=True),
            sa.Column("opened_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("hearing_date", sa.Date(), nullable=True),
            sa.Column("fine_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
        )
        created_violations = True
    ensure_index("violations", "ix_violations_id", ["id"], created=created_violations)
    ensure_index("violations", "ix_violations_status", ["status"], created=created_violations)

    created_violation_notices = False
    if not inspector.has_table("violation_notices"):
        op.create_table(
            "violation_notices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("violation_id", sa.Integer(), sa.ForeignKey("violations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sent_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("notice_type", sa.String(), nullable=False),
            sa.Column("template_key", sa.String(), nullable=False),
            sa.Column("subject", sa.String(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("pdf_path", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_violation_notices = True
    ensure_index("violation_notices", "ix_violation_notices_id", ["id"], created=created_violation_notices)

    created_appeals = False
    if not inspector.has_table("appeals"):
        op.create_table(
            "appeals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("violation_id", sa.Integer(), sa.ForeignKey("violations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("submitted_by_owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("decision_notes", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        created_appeals = True
    ensure_index("appeals", "ix_appeals_id", ["id"], created=created_appeals)

    created_arc_requests = False
    if not inspector.has_table("arc_requests"):
        op.create_table(
            "arc_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("project_type", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("decision_notes", sa.Text(), nullable=True),
            sa.Column("final_decision_at", sa.DateTime(), nullable=True),
            sa.Column("final_decision_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("revision_requested_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_arc_requests = True
    ensure_index("arc_requests", "ix_arc_requests_id", ["id"], created=created_arc_requests)
    ensure_index("arc_requests", "ix_arc_requests_status", ["status"], created=created_arc_requests)

    created_arc_attachments = False
    if not inspector.has_table("arc_attachments"):
        op.create_table(
            "arc_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("arc_request_id", sa.Integer(), sa.ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("original_filename", sa.String(), nullable=False),
            sa.Column("stored_filename", sa.String(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_arc_attachments = True
    ensure_index("arc_attachments", "ix_arc_attachments_id", ["id"], created=created_arc_attachments)

    created_arc_conditions = False
    if not inspector.has_table("arc_conditions"):
        op.create_table(
            "arc_conditions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("arc_request_id", sa.Integer(), sa.ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("condition_type", sa.String(), nullable=False, server_default="COMMENT"),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        created_arc_conditions = True
    ensure_index("arc_conditions", "ix_arc_conditions_id", ["id"], created=created_arc_conditions)

    created_arc_inspections = False
    if not inspector.has_table("arc_inspections"):
        op.create_table(
            "arc_inspections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("arc_request_id", sa.Integer(), sa.ForeignKey("arc_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("inspector_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("scheduled_date", sa.Date(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("result", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_arc_inspections = True
    ensure_index("arc_inspections", "ix_arc_inspections_id", ["id"], created=created_arc_inspections)

    if created_fine_schedules:
        fine_table = sa.table(
            "fine_schedules",
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("base_amount", sa.Numeric),
            sa.column("escalation_amount", sa.Numeric),
            sa.column("escalation_days", sa.Integer),
        )
        op.bulk_insert(
            fine_table,
            [
                {
                    "name": "Default Warning",
                    "description": "Initial warning with no immediate fine.",
                    "base_amount": "0",
                    "escalation_amount": None,
                    "escalation_days": None,
                },
                {
                    "name": "Standard Fine",
                    "description": "Initial fine with escalation after 30 days.",
                    "base_amount": "100",
                    "escalation_amount": "50",
                    "escalation_days": 30,
                },
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_arc_inspections_id", table_name="arc_inspections")
    op.drop_table("arc_inspections")
    op.drop_index("ix_arc_conditions_id", table_name="arc_conditions")
    op.drop_table("arc_conditions")
    op.drop_index("ix_arc_attachments_id", table_name="arc_attachments")
    op.drop_table("arc_attachments")
    op.drop_index("ix_arc_requests_status", table_name="arc_requests")
    op.drop_index("ix_arc_requests_id", table_name="arc_requests")
    op.drop_table("arc_requests")
    op.drop_index("ix_appeals_id", table_name="appeals")
    op.drop_table("appeals")
    op.drop_index("ix_violation_notices_id", table_name="violation_notices")
    op.drop_table("violation_notices")
    op.drop_index("ix_violations_status", table_name="violations")
    op.drop_index("ix_violations_id", table_name="violations")
    op.drop_table("violations")
    op.drop_index("ix_fine_schedules_id", table_name="fine_schedules")
    op.drop_table("fine_schedules")
