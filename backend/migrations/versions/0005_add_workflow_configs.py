"""add workflow configs

Revision ID: 0005_add_workflow_configs
Revises: 0004_add_template_types
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_add_workflow_configs"
down_revision = "0004_add_template_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_key", sa.String(), nullable=False),
        sa.Column("page_key", sa.String(), nullable=True),
        sa.Column("overrides_json", sa.JSON(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_workflow_configs_id"), "workflow_configs", ["id"], unique=False)
    op.create_index(op.f("ix_workflow_configs_page_key"), "workflow_configs", ["page_key"], unique=False)
    op.create_index(op.f("ix_workflow_configs_workflow_key"), "workflow_configs", ["workflow_key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_configs_workflow_key"), table_name="workflow_configs")
    op.drop_index(op.f("ix_workflow_configs_page_key"), table_name="workflow_configs")
    op.drop_index(op.f("ix_workflow_configs_id"), table_name="workflow_configs")
    op.drop_table("workflow_configs")
