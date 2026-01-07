"""click2mail integration fields

Revision ID: 8b0c74c7f5ce
Revises: b49d10178e79
Create Date: 2025-11-08 12:10:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "8b0c74c7f5ce"
down_revision = "b49d10178e79"
branch_labels = None
depends_on = None


def _column_exists(insp, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _column_exists(insp, "paperwork_items", "delivery_provider"):
        op.add_column("paperwork_items", sa.Column("delivery_provider", sa.String(), nullable=True))
    if not _column_exists(insp, "paperwork_items", "provider_job_id"):
        op.add_column("paperwork_items", sa.Column("provider_job_id", sa.String(), nullable=True))
    if not _column_exists(insp, "paperwork_items", "provider_status"):
        op.add_column("paperwork_items", sa.Column("provider_status", sa.String(), nullable=True))
    if not _column_exists(insp, "paperwork_items", "provider_meta"):
        op.add_column("paperwork_items", sa.Column("provider_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if _column_exists(insp, "paperwork_items", "provider_meta"):
        op.drop_column("paperwork_items", "provider_meta")
    if _column_exists(insp, "paperwork_items", "provider_status"):
        op.drop_column("paperwork_items", "provider_status")
    if _column_exists(insp, "paperwork_items", "provider_job_id"):
        op.drop_column("paperwork_items", "provider_job_id")
    if _column_exists(insp, "paperwork_items", "delivery_provider"):
        op.drop_column("paperwork_items", "delivery_provider")
