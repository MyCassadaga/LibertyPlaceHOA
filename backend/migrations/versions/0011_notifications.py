"""notifications table

Revision ID: 0011_notifications
Revises: 0010_elections
Create Date: 2025-11-04 18:32:00.000000
"""

import sqlalchemy as sa
from alembic import op


def _has_table(inspector, name: str) -> bool:
    return inspector.has_table(name)


def _ensure_index(inspector, table: str, name: str, columns: list[str]) -> None:
    existing = {index["name"] for index in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


revision = "0011_notifications"
down_revision = "0010_elections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("level", sa.String(length=32), nullable=False, server_default="info"),
            sa.Column("category", sa.String(length=64), nullable=True),
            sa.Column("link_url", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("read_at", sa.DateTime(), nullable=True),
        )
        inspector = sa.inspect(bind)

    _ensure_index(inspector, "notifications", "ix_notifications_user_id", ["user_id"])
    _ensure_index(inspector, "notifications", "ix_notifications_read_at", ["read_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "notifications"):
        existing_indexes = {index["name"] for index in inspector.get_indexes("notifications")}
        if "ix_notifications_read_at" in existing_indexes:
            op.drop_index("ix_notifications_read_at", table_name="notifications")
        if "ix_notifications_user_id" in existing_indexes:
            op.drop_index("ix_notifications_user_id", table_name="notifications")
        op.drop_table("notifications")
