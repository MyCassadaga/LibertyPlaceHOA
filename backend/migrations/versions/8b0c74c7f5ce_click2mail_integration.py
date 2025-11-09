"""click2mail integration fields

Revision ID: 8b0c74c7f5ce
Revises: b49d10178e79
Create Date: 2025-11-08 12:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b0c74c7f5ce"
down_revision = "b49d10178e79"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("paperwork_items", sa.Column("delivery_provider", sa.String(), nullable=True))
    op.add_column("paperwork_items", sa.Column("provider_job_id", sa.String(), nullable=True))
    op.add_column("paperwork_items", sa.Column("provider_status", sa.String(), nullable=True))
    op.add_column("paperwork_items", sa.Column("provider_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("paperwork_items", "provider_meta")
    op.drop_column("paperwork_items", "provider_status")
    op.drop_column("paperwork_items", "provider_job_id")
    op.drop_column("paperwork_items", "delivery_provider")
