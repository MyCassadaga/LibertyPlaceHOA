"""Add violation_messages table for two-way messaging

Revision ID: 1e0b5ac2d4a1
Revises: c2f94c1b2bf0
Create Date: 2025-12-17
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = "1e0b5ac2d4a1"
down_revision = "c2f94c1b2bf0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "violation_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("violation_id", sa.Integer(), sa.ForeignKey("violations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
    )
    op.create_index("ix_violation_messages_violation_id", "violation_messages", ["violation_id"])


def downgrade():
    op.drop_index("ix_violation_messages_violation_id", table_name="violation_messages")
    op.drop_table("violation_messages")
