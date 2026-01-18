"""add delivery status and provider response fields to communication messages

Revision ID: 0008_fix_message_delivery_tracking_and_backgroundtasks
Revises: 0007_add_communication_message_delivery_tracking
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_fix_message_delivery_tracking_and_backgroundtasks"
down_revision = "0007_add_communication_message_delivery_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("communication_messages", sa.Column("email_delivery_status", sa.String(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_provider_status_code", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("communication_messages", "email_provider_status_code")
    op.drop_column("communication_messages", "email_delivery_status")
