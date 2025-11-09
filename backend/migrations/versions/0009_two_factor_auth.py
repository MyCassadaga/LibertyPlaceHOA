"""two factor auth columns

Revision ID: 0009_two_factor_auth
Revises: 0008_multi_role_accounts
Create Date: 2025-11-03 13:20:00.000000
"""

import sqlalchemy as sa
from alembic import op


def _has_column(inspector, table: str, column: str) -> bool:
    return any(col["name"] == column for col in inspector.get_columns(table))


revision = "0009_two_factor_auth"
down_revision = "0008_multi_role_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "users", "two_factor_secret"):
        op.add_column("users", sa.Column("two_factor_secret", sa.String(), nullable=True))
    if not _has_column(inspector, "users", "two_factor_enabled"):
        op.add_column(
            "users",
            sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        op.execute("UPDATE users SET two_factor_enabled = 0 WHERE two_factor_enabled IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "users", "two_factor_enabled"):
        op.drop_column("users", "two_factor_enabled")
    if _has_column(inspector, "users", "two_factor_secret"):
        op.drop_column("users", "two_factor_secret")
