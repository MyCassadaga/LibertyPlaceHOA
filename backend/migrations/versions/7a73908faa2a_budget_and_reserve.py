"""budget_and_reserve

Revision ID: 7a73908faa2a
Revises: 0011_notifications
Create Date: 2025-11-08 10:53:11.096740
"""

from alembic import op
import sqlalchemy as sa



revision = '7a73908faa2a'
down_revision = '0011_notifications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "budgets" not in existing_tables:
        op.create_table(
            "budgets",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("year", sa.Integer(), nullable=False, unique=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
            sa.Column("home_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    created_budget_line_items = "budget_line_items" not in existing_tables
    if created_budget_line_items:
        op.create_table(
            "budget_line_items",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("is_reserve", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_budget_line_items_budget_id", "budget_line_items", ["budget_id"])
    else:
        _ensure_index(inspector, "budget_line_items", "ix_budget_line_items_budget_id", ["budget_id"])

    created_reserve_plan_items = "reserve_plan_items" not in existing_tables
    if created_reserve_plan_items:
        op.create_table(
            "reserve_plan_items",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("target_year", sa.Integer(), nullable=False),
            sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=False),
            sa.Column("inflation_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("current_funding", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_reserve_plan_items_budget_id", "reserve_plan_items", ["budget_id"])
    else:
        _ensure_index(inspector, "reserve_plan_items", "ix_reserve_plan_items_budget_id", ["budget_id"])

    created_budget_attachments = "budget_attachments" not in existing_tables
    if created_budget_attachments:
        op.create_table(
            "budget_attachments",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("budget_id", sa.Integer(), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("stored_path", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=128), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_budget_attachments_budget_id", "budget_attachments", ["budget_id"])
    else:
        _ensure_index(inspector, "budget_attachments", "ix_budget_attachments_budget_id", ["budget_id"])


def _ensure_index(
    inspector: sa.Inspector, table_name: str, index_name: str, columns: list[str]
) -> None:
    if table_name not in inspector.get_table_names():
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    op.drop_index("ix_budget_attachments_budget_id", table_name="budget_attachments")
    op.drop_table("budget_attachments")

    op.drop_index("ix_reserve_plan_items_budget_id", table_name="reserve_plan_items")
    op.drop_table("reserve_plan_items")

    op.drop_index("ix_budget_line_items_budget_id", table_name="budget_line_items")
    op.drop_table("budget_line_items")

    op.drop_table("budgets")
