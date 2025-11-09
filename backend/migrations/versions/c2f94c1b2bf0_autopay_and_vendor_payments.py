"""autopay and vendor payments scaffolding

Revision ID: c2f94c1b2bf0
Revises: a1b2c3d4e5f6
Create Date: 2025-02-05 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2f94c1b2bf0"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autopay_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("payment_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_type", sa.String(), nullable=False, server_default="STATEMENT_BALANCE"),
        sa.Column("fixed_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("funding_source_type", sa.String(), nullable=True),
        sa.Column("funding_source_mask", sa.String(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_payment_method_id", sa.String(), nullable=True),
        sa.Column("provider_status", sa.String(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", name="uq_autopay_owner"),
    )
    op.create_index(op.f("ix_autopay_enrollments_id"), "autopay_enrollments", ["id"], unique=False)

    op.create_table(
        "vendor_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=True),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("provider", sa.String(), nullable=False, server_default="STRIPE"),
        sa.Column("provider_status", sa.String(), nullable=True),
        sa.Column("provider_reference", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vendor_payments_id"), "vendor_payments", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vendor_payments_id"), table_name="vendor_payments")
    op.drop_table("vendor_payments")
    op.drop_index(op.f("ix_autopay_enrollments_id"), table_name="autopay_enrollments")
    op.drop_table("autopay_enrollments")
