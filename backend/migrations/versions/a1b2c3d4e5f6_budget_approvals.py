"""budget approvals and audit enhancements

Revision ID: a1b2c3d4e5f6
Revises: 9f3f6f0e9d2c
Create Date: 2025-11-08 13:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9f3f6f0e9d2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("budget_id", "user_id", name="uq_budget_user"),
    )


def downgrade() -> None:
    op.drop_table("budget_approvals")
