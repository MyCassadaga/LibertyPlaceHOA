"""Bank reconciliation tables.

Revision ID: 0005_bank_reconciliation
Revises: 0004_phase2_arc_violations
Create Date: 2024-11-01
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op


revision = "0005_bank_reconciliation"
down_revision = "0004_phase2_arc_violations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def ensure_index(table_name: str, index_name: str, columns: list[str], created: bool = False) -> None:
        if created:
            op.create_index(index_name, table_name, columns, unique=False)
            return
        try:
            existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
        except sa.exc.NoSuchTableError:
            existing = set()
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, unique=False)

    created_reconciliations = False
    if not inspector.has_table("reconciliations"):
        op.create_table(
            "reconciliations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("statement_date", sa.Date(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("total_transactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("matched_transactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unmatched_transactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("matched_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("unmatched_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_reconciliations = True
    ensure_index("reconciliations", "ix_reconciliations_id", ["id"], created=created_reconciliations)

    created_transactions = False
    if not inspector.has_table("bank_transactions"):
        op.create_table(
            "bank_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reconciliation_id", sa.Integer(), sa.ForeignKey("reconciliations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("transaction_date", sa.Date(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("reference", sa.String(), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
            sa.Column("matched_payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=True),
            sa.Column("matched_invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
            sa.Column("source_file", sa.String(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, default=datetime.utcnow, server_default=sa.func.now()),
        )
        created_transactions = True
    ensure_index("bank_transactions", "ix_bank_transactions_id", ["id"], created=created_transactions)
    ensure_index("bank_transactions", "ix_bank_transactions_status", ["status"], created=created_transactions)
    ensure_index("bank_transactions", "ix_bank_transactions_transaction_date", ["transaction_date"], created=created_transactions)


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_transaction_date", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_status", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_id", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ix_reconciliations_id", table_name="reconciliations")
    op.drop_table("reconciliations")
