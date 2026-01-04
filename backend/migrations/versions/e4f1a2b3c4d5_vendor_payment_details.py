"""add vendor payment details

Revision ID: e4f1a2b3c4d5
Revises: d3f1c2b4a9ef
Create Date: 2025-02-20 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f1a2b3c4d5"
down_revision: Union[str, None] = "d3f1c2b4a9ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("vendor_payments") as batch_op:
        batch_op.add_column(sa.Column("payment_method", sa.String(), nullable=False, server_default="OTHER"))
        batch_op.add_column(sa.Column("check_number", sa.String(), nullable=True))
        batch_op.alter_column("memo", new_column_name="notes", existing_type=sa.Text())
        batch_op.alter_column("payment_method", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("vendor_payments") as batch_op:
        batch_op.alter_column("notes", new_column_name="memo", existing_type=sa.Text())
        batch_op.drop_column("check_number")
        batch_op.drop_column("payment_method")
