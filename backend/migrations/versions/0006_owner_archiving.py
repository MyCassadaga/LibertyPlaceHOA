"""owner and user archiving support

Revision ID: 0006_owner_archiving
Revises: 0005_bank_reconciliation
Create Date: 2024-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import Boolean


# revision identifiers, used by Alembic.
revision = "0006_owner_archiving"
down_revision = "0005_bank_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    owner_columns = {column["name"] for column in inspector.get_columns("owners")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    if "is_archived" not in owner_columns:
        op.add_column(
            "owners",
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        owners = table("owners", column("is_archived", Boolean))
        op.execute(owners.update().values(is_archived=False))

    if "archived_at" not in owner_columns:
        op.add_column("owners", sa.Column("archived_at", sa.DateTime(), nullable=True))

    if "archived_by_user_id" not in owner_columns:
        op.add_column("owners", sa.Column("archived_by_user_id", sa.Integer(), nullable=True))

    if "archived_reason" not in owner_columns:
        op.add_column("owners", sa.Column("archived_reason", sa.Text(), nullable=True))

    if "former_lot" not in owner_columns:
        op.add_column("owners", sa.Column("former_lot", sa.String(), nullable=True))

    if "is_active" not in user_columns:
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        users = table("users", column("is_active", Boolean))
        op.execute(users.update().values(is_active=True))

    if "archived_at" not in user_columns:
        op.add_column("users", sa.Column("archived_at", sa.DateTime(), nullable=True))

    if "archived_reason" not in user_columns:
        op.add_column("users", sa.Column("archived_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("owners", "former_lot")
    op.drop_column("owners", "archived_reason")
    op.drop_column("owners", "archived_by_user_id")
    op.drop_column("owners", "archived_at")
    op.drop_column("owners", "is_archived")

    op.drop_column("users", "archived_reason")
    op.drop_column("users", "archived_at")
    op.drop_column("users", "is_active")
