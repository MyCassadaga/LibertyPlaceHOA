"""budget_line_item_sources

Revision ID: b7c1d2e3f4a5
Revises: e4f1a2b3c4d5
Create Date: 2025-11-10 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c1d2e3f4a5"
down_revision = "e4f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("budget_line_items", sa.Column("source_type", sa.String(length=64), nullable=True))
    op.add_column("budget_line_items", sa.Column("source_id", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_budget_line_items_source",
        "budget_line_items",
        ["budget_id", "source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_budget_line_items_source", "budget_line_items", type_="unique")
    op.drop_column("budget_line_items", "source_id")
    op.drop_column("budget_line_items", "source_type")
