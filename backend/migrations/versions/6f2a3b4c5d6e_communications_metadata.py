"""communications metadata

Revision ID: 6f2a3b4c5d6e
Revises: d3f1c2b4a9ef
Create Date: 2025-11-12 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "6f2a3b4c5d6e"
down_revision = "d3f1c2b4a9ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("announcements") as batch_op:
        batch_op.add_column(sa.Column("recipient_snapshot", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("sender_snapshot", sa.JSON(), nullable=True))

    with op.batch_alter_table("email_broadcasts") as batch_op:
        batch_op.add_column(sa.Column("delivery_methods", sa.JSON(), nullable=False, server_default='["email"]'))
        batch_op.add_column(sa.Column("sender_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("email_broadcasts") as batch_op:
        batch_op.drop_column("sender_snapshot")
        batch_op.drop_column("delivery_methods")

    with op.batch_alter_table("announcements") as batch_op:
        batch_op.drop_column("sender_snapshot")
        batch_op.drop_column("recipient_count")
        batch_op.drop_column("recipient_snapshot")
