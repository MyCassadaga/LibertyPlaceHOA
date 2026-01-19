"""widen alembic version column length

Revision ID: 0009_widen_alembic_version_num
Revises: 0008_fix_message_delivery_tracking_and_backgroundtasks
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_widen_alembic_version_num"
down_revision = "0008_fix_message_delivery_tracking_and_backgroundtasks"
branch_labels = None
depends_on = None


TARGET_LENGTH = 255
PREVIOUS_LENGTH = 32


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("alembic_version") as batch_op:
            batch_op.alter_column(
                "version_num",
                type_=sa.String(TARGET_LENGTH),
                existing_type=sa.String(PREVIOUS_LENGTH),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            "alembic_version",
            "version_num",
            type_=sa.String(TARGET_LENGTH),
            existing_type=sa.String(PREVIOUS_LENGTH),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("alembic_version") as batch_op:
            batch_op.alter_column(
                "version_num",
                type_=sa.String(PREVIOUS_LENGTH),
                existing_type=sa.String(TARGET_LENGTH),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            "alembic_version",
            "version_num",
            type_=sa.String(PREVIOUS_LENGTH),
            existing_type=sa.String(TARGET_LENGTH),
            existing_nullable=False,
        )
