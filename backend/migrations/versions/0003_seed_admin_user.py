"""seed admin user

Revision ID: 0003_seed_admin_user
Revises: 0002_make_audit_actor_nullable
Create Date: 2026-01-07 19:05:00.000000
"""

from datetime import datetime

from alembic import op
from passlib.context import CryptContext
import sqlalchemy as sa


revision = "0003_seed_admin_user"
down_revision = "0002_make_audit_actor_nullable"
branch_labels = None
depends_on = None


EMAIL = "admin@libertyplacehoa.com"
FULL_NAME = "Kevin Nourse"
ROLE_NAME = "SYSADMIN"
ROLE_DESCRIPTION = "System administrator with full access"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_role_id(conn, roles_table):
    role_id = conn.execute(
        sa.select(roles_table.c.id).where(roles_table.c.name == ROLE_NAME)
    ).scalar()
    if role_id is not None:
        return role_id
    result = conn.execute(
        roles_table.insert().values(name=ROLE_NAME, description=ROLE_DESCRIPTION)
    )
    return result.inserted_primary_key[0]


def upgrade() -> None:
    conn = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("role_id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
        sa.column("is_active", sa.Boolean),
        sa.column("two_factor_enabled", sa.Boolean),
    )
    user_roles_table = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )

    role_id = _get_role_id(conn, roles_table)
    user_id = conn.execute(
        sa.select(users_table.c.id).where(users_table.c.email == EMAIL)
    ).scalar()
    if user_id is None:
        now = datetime.utcnow()
        result = conn.execute(
            users_table.insert().values(
                email=EMAIL,
                full_name=FULL_NAME,
                hashed_password=pwd_context.hash("changeme"),
                role_id=role_id,
                created_at=now,
                updated_at=now,
                is_active=True,
                two_factor_enabled=False,
            )
        )
        user_id = result.inserted_primary_key[0]
    else:
        conn.execute(
            users_table.update()
            .where(users_table.c.id == user_id)
            .values(role_id=role_id)
        )

    existing_link = conn.execute(
        sa.select(user_roles_table.c.user_id).where(
            sa.and_(
                user_roles_table.c.user_id == user_id,
                user_roles_table.c.role_id == role_id,
            )
        )
    ).scalar()
    if existing_link is None:
        conn.execute(user_roles_table.insert().values(user_id=user_id, role_id=role_id))


def downgrade() -> None:
    conn = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
    )
    user_roles_table = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )

    role_id = conn.execute(
        sa.select(roles_table.c.id).where(roles_table.c.name == ROLE_NAME)
    ).scalar()
    user_id = conn.execute(
        sa.select(users_table.c.id).where(
            sa.and_(users_table.c.email == EMAIL, users_table.c.full_name == FULL_NAME)
        )
    ).scalar()
    if role_id is None or user_id is None:
        return
    conn.execute(
        user_roles_table.delete().where(
            sa.and_(
                user_roles_table.c.user_id == user_id,
                user_roles_table.c.role_id == role_id,
            )
        )
    )
    conn.execute(users_table.delete().where(users_table.c.id == user_id))
