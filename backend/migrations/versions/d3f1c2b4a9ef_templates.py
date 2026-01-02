"""template library

Revision ID: d3f1c2b4a9ef
Revises: 1e0b5ac2d4a1
Create Date: 2025-11-08 12:15:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d3f1c2b4a9ef"
down_revision = "1e0b5ac2d4a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_templates_id"), "templates", ["id"], unique=False)
    op.create_index("ix_templates_type", "templates", ["type"], unique=False)
    op.create_index("ix_templates_is_archived", "templates", ["is_archived"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_templates_is_archived", table_name="templates")
    op.drop_index("ix_templates_type", table_name="templates")
    op.drop_index(op.f("ix_templates_id"), table_name="templates")
    op.drop_table("templates")
