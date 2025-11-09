"""governance documents and meetings

Revision ID: 9f3f6f0e9d2c
Revises: 8b0c74c7f5ce
Create Date: 2025-11-08 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f3f6f0e9d2c"
down_revision = "8b0c74c7f5ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("document_folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "governance_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("folder_id", sa.Integer(), sa.ForeignKey("document_folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("zoom_link", sa.String(), nullable=True),
        sa.Column("minutes_file_path", sa.String(), nullable=True),
        sa.Column("minutes_content_type", sa.String(), nullable=True),
        sa.Column("minutes_file_size", sa.Integer(), nullable=True),
        sa.Column("minutes_uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.add_column("paperwork_items", sa.Column("pdf_path", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("paperwork_items", "pdf_path")
    op.drop_table("meetings")
    op.drop_table("governance_documents")
    op.drop_table("document_folders")
