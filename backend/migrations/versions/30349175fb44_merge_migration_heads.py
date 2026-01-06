"""merge migration heads

Revision ID: 30349175fb44
Revises: 0016_arc_request_notification_columns, b7c1d2e3f4a5
Create Date: 2026-01-06 23:12:06.620574
"""

from alembic import op
import sqlalchemy as sa



revision = '30349175fb44'
down_revision = ('0016_arc_request_notification_columns', 'b7c1d2e3f4a5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
