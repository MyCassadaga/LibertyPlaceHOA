"""Baseline schema reset.

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-01-07 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect

from backend.config import Base
from backend import models  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _drop_all_tables(connection):
    inspector = inspect(connection)
    table_names = inspector.get_table_names()

    if connection.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")

    for table_name in table_names:
        if table_name == "alembic_version":
            continue
        if connection.dialect.name == "postgresql":
            op.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        else:
            op.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    if connection.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def upgrade():
    connection = op.get_bind()
    _drop_all_tables(connection)
    Base.metadata.create_all(bind=connection)


def downgrade():
    connection = op.get_bind()
    _drop_all_tables(connection)
