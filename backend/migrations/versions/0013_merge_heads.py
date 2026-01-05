"""Merge multiple Alembic heads.

Revision ID: 0013_merge_heads
Revises: 0012_communication_messages, 6f2a3b4c5d6e, a1b2c3d4e5f6, e4c1c3b7a2f1
Create Date: 2025-03-11
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0013_merge_heads"
down_revision = (
    "0012_communication_messages",
    "6f2a3b4c5d6e",
    "a1b2c3d4e5f6",
    "e4c1c3b7a2f1",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
