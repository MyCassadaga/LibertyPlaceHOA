"""multi role accounts

Revision ID: 0008_multi_role_accounts
Revises: 0007_owner_user_links
Create Date: 2024-12-15 00:00:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0008_multi_role_accounts"
down_revision = "0007_owner_user_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    bind = op.get_bind()
    existing_assignments = bind.execute(
        sa.text("SELECT id as user_id, role_id FROM users WHERE role_id IS NOT NULL")
    ).fetchall()

    if existing_assignments:
        user_roles_table = sa.table(
            "user_roles",
            sa.column("user_id", sa.Integer),
            sa.column("role_id", sa.Integer),
            sa.column("assigned_at", sa.DateTime),
        )
        op.bulk_insert(
            user_roles_table,
            [
                {
                    "user_id": row.user_id,
                    "role_id": row.role_id,
                    "assigned_at": datetime.utcnow(),
                }
                for row in existing_assignments
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")
