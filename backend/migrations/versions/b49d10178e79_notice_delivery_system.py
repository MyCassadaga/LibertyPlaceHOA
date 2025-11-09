"""notice_delivery_system

Revision ID: b49d10178e79
Revises: 7a73908faa2a
Create Date: 2025-11-08 11:19:11.720683
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Boolean, Text, DateTime, text

NOTICE_SEED = [
    {
        'code': 'ANNUAL_MEETING',
        'name': 'Annual Meeting Notice',
        'description': 'Required notice for annual meetings.',
        'allow_electronic': True,
        'requires_paper': False,
        'default_delivery': 'AUTO',
    },
    {
        'code': 'NEWSLETTER',
        'name': 'Newsletter',
        'description': 'General community newsletter.',
        'allow_electronic': True,
        'requires_paper': False,
        'default_delivery': 'AUTO',
    },
    {
        'code': 'DELINQUENCY_FIRST',
        'name': 'Delinquency (First Notice)',
        'description': 'First delinquency reminder.',
        'allow_electronic': True,
        'requires_paper': True,
        'default_delivery': 'AUTO',
    },
    {
        'code': 'LIEN_NOTICE',
        'name': 'Lien Notice',
        'description': 'Lien filing notice.',
        'allow_electronic': True,
        'requires_paper': True,
        'default_delivery': 'PAPER_ONLY',
    },
    {
        'code': 'FINE_IMPOSITION',
        'name': 'Fine Imposition Notice',
        'description': 'Notice of fine imposed.',
        'allow_electronic': True,
        'requires_paper': True,
        'default_delivery': 'AUTO',
    },
    {
        'code': 'VIOLATION_NOTICE',
        'name': 'Violation Notice',
        'description': 'Covenant violation notice.',
        'allow_electronic': True,
        'requires_paper': True,
        'default_delivery': 'AUTO',
    },
]



revision = 'b49d10178e79'
down_revision = '7a73908faa2a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('notice_types'):
        op.create_table(
            'notice_types',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False, unique=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('allow_electronic', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('requires_paper', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('default_delivery', sa.String(length=32), nullable=False, server_default='AUTO'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)

    columns = [col['name'] for col in inspector.get_columns('owners')]
    if 'delivery_preference_global' not in columns:
        op.add_column(
            'owners',
            sa.Column('delivery_preference_global', sa.String(length=32), nullable=False, server_default='AUTO'),
        )
        op.create_index('ix_owners_delivery_preference_global', 'owners', ['delivery_preference_global'])

    if not inspector.has_table('notices'):
        op.create_table(
            'notices',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('owner_id', sa.Integer(), sa.ForeignKey('owners.id', ondelete='CASCADE'), nullable=False),
            sa.Column('notice_type_id', sa.Integer(), sa.ForeignKey('notice_types.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('subject', sa.String(length=255), nullable=False),
            sa.Column('body_html', sa.Text(), nullable=False),
            sa.Column('delivery_channel', sa.String(length=32), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('sent_email_at', sa.DateTime(), nullable=True),
            sa.Column('mailed_at', sa.DateTime(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_notices_owner_id', 'notices', ['owner_id'])
        op.create_index('ix_notices_notice_type', 'notices', ['notice_type_id'])
        inspector = sa.inspect(bind)

    if not inspector.has_table('paperwork_items'):
        op.create_table(
            'paperwork_items',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('notice_id', sa.Integer(), sa.ForeignKey('notices.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('owner_id', sa.Integer(), sa.ForeignKey('owners.id', ondelete='CASCADE'), nullable=False),
            sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
            sa.Column('claimed_by_board_member_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('claimed_at', sa.DateTime(), nullable=True),
            sa.Column('mailed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_paperwork_items_status_required', 'paperwork_items', ['status', 'required'])

    notice_types_table = table(
        'notice_types',
        column('code', String),
        column('name', String),
        column('description', Text),
        column('allow_electronic', Boolean),
        column('requires_paper', Boolean),
        column('default_delivery', String),
    )

    existing_codes = {row[0] for row in bind.execute(text("SELECT code FROM notice_types"))}
    to_insert = [entry for entry in NOTICE_SEED if entry['code'] not in existing_codes]
    if to_insert:
        op.bulk_insert(notice_types_table, to_insert)

    columns = [col['name'] for col in inspector.get_columns('owners')]
    # leave defaults intact for SQLite


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('paperwork_items'):
        op.drop_index('ix_paperwork_items_status_required', table_name='paperwork_items')
        op.drop_table('paperwork_items')

    if inspector.has_table('notices'):
        op.drop_index('ix_notices_notice_type', table_name='notices')
        op.drop_index('ix_notices_owner_id', table_name='notices')
        op.drop_table('notices')

    columns = [col['name'] for col in inspector.get_columns('owners')]
    if 'delivery_preference_global' in columns:
        op.drop_index('ix_owners_delivery_preference_global', table_name='owners')
        op.drop_column('owners', 'delivery_preference_global')

    if inspector.has_table('notice_types'):
        op.drop_table('notice_types')
