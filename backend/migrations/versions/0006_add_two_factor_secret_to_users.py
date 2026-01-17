"""add two factor secret to users

Revision ID: 0006_add_two_factor_secret_to_users
Revises: 0005_add_workflow_configs
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "0006_add_two_factor_secret_to_users"
down_revision = "0005_add_workflow_configs"
branch_labels = None
depends_on = None


def _has_column(connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    connection = op.get_bind()
    if not _has_column(connection, "users", "two_factor_secret"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("two_factor_secret", sa.String(), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if _has_column(connection, "users", "two_factor_secret"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("two_factor_secret")
