"""Add contract attachment metadata.

Revision ID: e4c1c3b7a2f1
Revises: d3f1c2b4a9ef_templates
Create Date: 2025-01-15

"""

from alembic import op
import sqlalchemy as sa


revision = "e4c1c3b7a2f1"
down_revision = "d3f1c2b4a9ef_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("attachment_file_name", sa.String(), nullable=True))
    op.add_column("contracts", sa.Column("attachment_content_type", sa.String(), nullable=True))
    op.add_column("contracts", sa.Column("attachment_file_size", sa.Integer(), nullable=True))
    op.add_column("contracts", sa.Column("attachment_uploaded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("contracts", "attachment_uploaded_at")
    op.drop_column("contracts", "attachment_file_size")
    op.drop_column("contracts", "attachment_content_type")
    op.drop_column("contracts", "attachment_file_name")
