"""two factor auth columns

Revision ID: 0009_two_factor_auth
Revises: 0008_multi_role_accounts
Create Date: 2025-11-03 13:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_two_factor_auth"
down_revision = "0008_multi_role_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("two_factor_secret", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.execute("UPDATE users SET two_factor_enabled = 0 WHERE two_factor_enabled IS NULL")


def downgrade() -> None:
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "two_factor_secret")
