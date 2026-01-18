"""add communication message delivery tracking fields

Revision ID: 0007_add_communication_message_delivery_tracking
Revises: 0006_add_two_factor_secret_to_users
Create Date: 2025-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_add_communication_message_delivery_tracking"
down_revision = "0006_add_two_factor_secret_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("communication_messages", sa.Column("email_queued_at", sa.DateTime(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_send_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_sent_at", sa.DateTime(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_failed_at", sa.DateTime(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_last_error", sa.Text(), nullable=True))
    op.add_column("communication_messages", sa.Column("email_provider_message_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("communication_messages", "email_provider_message_id")
    op.drop_column("communication_messages", "email_last_error")
    op.drop_column("communication_messages", "email_failed_at")
    op.drop_column("communication_messages", "email_sent_at")
    op.drop_column("communication_messages", "email_send_attempted_at")
    op.drop_column("communication_messages", "email_queued_at")
