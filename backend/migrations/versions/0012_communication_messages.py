"""communication messages table

Revision ID: 0012_communication_messages
Revises: 0011_notifications
Create Date: 2025-11-05 10:15:00.000000
"""

import sqlalchemy as sa
from alembic import op


def _has_table(inspector, name: str) -> bool:
    return inspector.has_table(name)


revision = "0012_communication_messages"
down_revision = "0011_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "communication_messages"):
        op.create_table(
            "communication_messages",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("message_type", sa.String(length=32), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("segment", sa.String(length=64), nullable=True),
            sa.Column("delivery_methods", sa.JSON(), nullable=False),
            sa.Column("recipient_snapshot", sa.JSON(), nullable=False),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pdf_path", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        )
        op.create_index("ix_communication_messages_id", "communication_messages", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "communication_messages"):
        existing_indexes = {index["name"] for index in inspector.get_indexes("communication_messages")}
        if "ix_communication_messages_id" in existing_indexes:
            op.drop_index("ix_communication_messages_id", table_name="communication_messages")
        op.drop_table("communication_messages")
