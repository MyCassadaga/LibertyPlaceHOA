"""Create email broadcasts table.

Revision ID: 0003_email_broadcasts
Revises: 0002_billing_policy
Create Date: 2024-10-27
"""

import sqlalchemy as sa
from alembic import op


revision = "0003_email_broadcasts"
down_revision = "0002_billing_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "email_broadcasts" not in tables:
        op.create_table(
            "email_broadcasts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("subject", sa.String(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("segment", sa.String(), nullable=False),
            sa.Column("recipient_snapshot", sa.JSON(), nullable=False),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        )
        op.create_index(op.f("ix_email_broadcasts_id"), "email_broadcasts", ["id"], unique=False)
    else:
        existing_columns = {col["name"] for col in inspector.get_columns("email_broadcasts")}
        if "recipient_count" not in existing_columns:
            op.add_column(
                "email_broadcasts",
                sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if "created_at" not in existing_columns:
            op.add_column(
                "email_broadcasts",
                sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            )
        indexes = {index["name"] for index in inspector.get_indexes("email_broadcasts")}
        if "ix_email_broadcasts_id" not in indexes:
            op.create_index(op.f("ix_email_broadcasts_id"), "email_broadcasts", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_broadcasts_id"), table_name="email_broadcasts")
    op.drop_table("email_broadcasts")
