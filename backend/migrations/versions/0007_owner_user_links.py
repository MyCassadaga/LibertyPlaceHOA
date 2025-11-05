"""owner user link table

Revision ID: 0007_owner_user_links
Revises: 0006_owner_archiving
Create Date: 2024-05-21 00:00:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0007_owner_user_links"
down_revision = "0006_owner_archiving"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("owner_user_links"):
        op.create_table(
            "owner_user_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("link_type", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
            sa.UniqueConstraint("owner_id", "user_id", name="uq_owner_user_links_owner_user"),
        )
        op.create_index("ix_owner_user_links_owner_id", "owner_user_links", ["owner_id"], unique=False)
        op.create_index("ix_owner_user_links_user_id", "owner_user_links", ["user_id"], unique=False)

        # Backfill based on email matches so existing homeowners stay linked
        connection = bind
        roles = {
            row.id: row.name
            for row in connection.execute(sa.text("SELECT id, name FROM roles"))
        }

        owner_rows = connection.execute(
            sa.text("SELECT id, primary_email, secondary_email, is_archived FROM owners")
        ).fetchall()

        user_rows = connection.execute(
            sa.text("SELECT id, email, role_id FROM users")
        ).fetchall()
        users_by_email = {}
        for user in user_rows:
            email = (user.email or "").lower()
            if email:
                users_by_email.setdefault(email, []).append(user)

        insert_rows = []
        linked_homeowner_users: set[int] = set()
        for owner in owner_rows:
            emails = {
                (owner.primary_email or "").lower(),
                (owner.secondary_email or "").lower(),
            }
            emails = {email for email in emails if email}
            for email in emails:
                candidates = users_by_email.get(email, [])
                for user in candidates:
                    if user.role_id and roles.get(user.role_id) == "HOMEOWNER" and user.id in linked_homeowner_users:
                        continue
                    insert_rows.append(
                        {
                            "owner_id": owner.id,
                            "user_id": user.id,
                            "link_type": "PRIMARY" if roles.get(user.role_id) == "HOMEOWNER" else None,
                        }
                    )
                    if roles.get(user.role_id) == "HOMEOWNER":
                        linked_homeowner_users.add(user.id)
                    break

        if insert_rows:
            op.bulk_insert(
                sa.table(
                    "owner_user_links",
                    sa.column("owner_id", sa.Integer),
                    sa.column("user_id", sa.Integer),
                    sa.column("link_type", sa.String),
                ),
                insert_rows,
            )


def downgrade() -> None:
    op.drop_index("ix_owner_user_links_user_id", table_name="owner_user_links")
    op.drop_index("ix_owner_user_links_owner_id", table_name="owner_user_links")
    op.drop_constraint("uq_owner_user_links_owner_user", "owner_user_links", type_="unique")
    op.drop_table("owner_user_links")
