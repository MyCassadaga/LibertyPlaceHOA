"""Merge alembic heads after vendor payment details.

Revision ID: 0014_merge_heads_vendor_payments
Revises: 0013_merge_heads, e4f1a2b3c4d5
Create Date: 2025-03-11
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0014_merge_heads_vendor_payments"
down_revision = ("0013_merge_heads", "e4f1a2b3c4d5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
