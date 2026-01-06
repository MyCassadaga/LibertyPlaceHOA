"""Ensure ARC request notification columns exist.

Revision ID: 0016_arc_request_notification_columns
Revises: 0015_arc_reviews_and_notifications
Create Date: 2025-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_arc_request_notification_columns"
down_revision = "0015_arc_reviews_and_notifications"
branch_labels = None
depends_on = None


def _get_arc_request_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("arc_requests")}


def upgrade() -> None:
    columns = _get_arc_request_columns()
    if "decision_notified_at" not in columns:
        op.add_column("arc_requests", sa.Column("decision_notified_at", sa.DateTime(), nullable=True))
    if "decision_notified_status" not in columns:
        op.add_column("arc_requests", sa.Column("decision_notified_status", sa.String(), nullable=True))


def downgrade() -> None:
    columns = _get_arc_request_columns()
    if "decision_notified_status" in columns:
        op.drop_column("arc_requests", "decision_notified_status")
    if "decision_notified_at" in columns:
        op.drop_column("arc_requests", "decision_notified_at")
