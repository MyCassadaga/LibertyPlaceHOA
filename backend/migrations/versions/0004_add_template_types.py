"""add template types

Revision ID: 0004_add_template_types
Revises: 0003_seed_admin_user
Create Date: 2026-01-08 00:00:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0004_add_template_types"
down_revision = "0003_seed_admin_user"
branch_labels = None
depends_on = None


TEMPLATE_TYPES = [
    {
        "code": "ANNOUNCEMENT",
        "label": "Announcement",
        "definition": "General announcements shared with the community.",
    },
    {
        "code": "BROADCAST",
        "label": "Broadcast",
        "definition": "Broad communications sent to a selected segment.",
    },
    {
        "code": "NOTICE",
        "label": "Notice",
        "definition": "Formal notices sent to homeowners.",
    },
    {
        "code": "VIOLATION_NOTICE",
        "label": "Violation Notice",
        "definition": "Notices related to covenant violations.",
    },
    {
        "code": "ARC_REQUEST",
        "label": "ARC Request",
        "definition": "ARC decision messages for architectural review requests.",
    },
    {
        "code": "LEGAL",
        "label": "Legal",
        "definition": "Legal communications managed by the board or counsel.",
    },
    {
        "code": "BILLING_NOTICE",
        "label": "Billing Notice",
        "definition": "Emails sent to individuals as a result of billing.",
    },
]


def upgrade() -> None:
    op.create_table(
        "template_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_template_types_code"), "template_types", ["code"], unique=False)
    op.create_index(op.f("ix_template_types_id"), "template_types", ["id"], unique=False)

    conn = op.get_bind()
    template_types_table = sa.table(
        "template_types",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("definition", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = datetime.utcnow()
    for entry in TEMPLATE_TYPES:
        exists = conn.execute(
            sa.select(template_types_table.c.code).where(template_types_table.c.code == entry["code"])
        ).scalar_one_or_none()
        if exists:
            continue
        conn.execute(
            template_types_table.insert().values(
                code=entry["code"],
                label=entry["label"],
                definition=entry["definition"],
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_template_types_id"), table_name="template_types")
    op.drop_index(op.f("ix_template_types_code"), table_name="template_types")
    op.drop_table("template_types")
