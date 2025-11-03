"""Add billing policy, late fee tiers, and reminder tracking.

Revision ID: 0002_billing_policy
Revises: 0001_initial
Create Date: 2024-10-27
"""

import sqlalchemy as sa
from alembic import op


def _get_inspector():
    bind = op.get_bind()
    return sa.inspect(bind)


revision = "0002_billing_policy"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = _get_inspector()
    tables = set(inspector.get_table_names())

    invoice_columns = set()
    if "invoices" in tables:
        invoice_columns = {col["name"] for col in inspector.get_columns("invoices")}

    if "original_amount" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("original_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        )
        op.execute(
            "UPDATE invoices SET original_amount = amount WHERE original_amount = 0 OR original_amount IS NULL"
        )
        bind = op.get_bind()
        if bind.dialect.name != "sqlite":
            op.alter_column("invoices", "original_amount", server_default=None)

    if "late_fee_total" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("late_fee_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        )
        op.execute("UPDATE invoices SET late_fee_total = 0 WHERE late_fee_total IS NULL")
        if bind.dialect.name != "sqlite":
            op.alter_column("invoices", "late_fee_total", server_default="0")

    if "last_late_fee_applied_at" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("last_late_fee_applied_at", sa.DateTime(), nullable=True),
        )

    if "last_reminder_sent_at" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("last_reminder_sent_at", sa.DateTime(), nullable=True),
        )

    if "billing_policies" not in tables:
        op.create_table(
            "billing_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("dunning_schedule_days", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_billing_policies_id"), "billing_policies", ["id"], unique=False)

    late_fee_tier_constraints = set()
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if "late_fee_tiers" not in tables:
        op.create_table(
            "late_fee_tiers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "policy_id", sa.Integer(), sa.ForeignKey("billing_policies.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("sequence_order", sa.Integer(), nullable=False),
            sa.Column("trigger_days_after_grace", sa.Integer(), nullable=False),
            sa.Column("fee_type", sa.String(), nullable=False, server_default="flat"),
            sa.Column("fee_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("fee_percent", sa.Float(), nullable=False, server_default="0"),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f("ix_late_fee_tiers_id"), "late_fee_tiers", ["id"], unique=False)
    else:
        late_fee_tier_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("late_fee_tiers")
        }

    if is_sqlite:
        # SQLite doesn't support ALTER COLUMN DROP/SET DEFAULT; skip alterations already handled by server_default
        pass
    elif "uq_late_fee_tiers_policy_sequence" not in late_fee_tier_constraints:
        op.create_unique_constraint(
            "uq_late_fee_tiers_policy_sequence",
            "late_fee_tiers",
            ["policy_id", "sequence_order"],
        )

    invoice_late_fee_constraints = set()
    if "invoice_late_fees" not in tables:
        op.create_table(
            "invoice_late_fees",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tier_id", sa.Integer(), sa.ForeignKey("late_fee_tiers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("applied_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("fee_amount", sa.Numeric(10, 2), nullable=False),
        )
        op.create_index(op.f("ix_invoice_late_fees_id"), "invoice_late_fees", ["id"], unique=False)
    else:
        invoice_late_fee_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("invoice_late_fees")
        }

    if not is_sqlite and "uq_invoice_late_fees_invoice_tier" not in invoice_late_fee_constraints:
        op.create_unique_constraint(
            "uq_invoice_late_fees_invoice_tier",
            "invoice_late_fees",
            ["invoice_id", "tier_id"],
        )


def downgrade() -> None:
    op.alter_column("invoices", "late_fee_total", server_default=None)
    op.drop_constraint("uq_invoice_late_fees_invoice_tier", "invoice_late_fees", type_="unique")
    op.drop_index(op.f("ix_invoice_late_fees_id"), table_name="invoice_late_fees")
    op.drop_table("invoice_late_fees")
    op.drop_constraint("uq_late_fee_tiers_policy_sequence", "late_fee_tiers", type_="unique")
    op.drop_index(op.f("ix_late_fee_tiers_id"), table_name="late_fee_tiers")
    op.drop_table("late_fee_tiers")
    op.drop_index(op.f("ix_billing_policies_id"), table_name="billing_policies")
    op.drop_table("billing_policies")
    op.drop_column("invoices", "last_reminder_sent_at")
    op.drop_column("invoices", "last_late_fee_applied_at")
    op.drop_column("invoices", "late_fee_total")
    op.drop_column("invoices", "original_amount")
