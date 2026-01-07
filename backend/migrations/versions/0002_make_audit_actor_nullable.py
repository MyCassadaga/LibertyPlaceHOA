"""make audit actor nullable

Revision ID: 0002_make_audit_actor_nullable
Revises: 0001_baseline
Create Date: 2026-01-07 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_make_audit_actor_nullable"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.alter_column(
            "actor_user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.alter_column(
            "actor_user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
