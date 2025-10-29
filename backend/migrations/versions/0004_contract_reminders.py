"""Create reminders table for contract renewal warnings.

Revision ID: 0004_contract_reminders
Revises: 0003_email_broadcasts
Create Date: 2024-10-27
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op


revision = "0004_contract_reminders"
down_revision = "0003_email_broadcasts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reminders" in tables:
        return

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reminder_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_reminders_id"), "reminders", ["id"], unique=False)
    op.create_index("ix_reminders_entity_type_id", "reminders", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_entity_type_id", table_name="reminders")
    op.drop_index(op.f("ix_reminders_id"), table_name="reminders")
    op.drop_table("reminders")
