"""elections and voting tables

Revision ID: 0010_elections
Revises: 0009_two_factor_auth
Create Date: 2025-11-04 16:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


def _ensure_index(inspector, table: str, name: str, columns: list[str]) -> None:
    existing = {index['name'] for index in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


def _has_table(inspector, name: str) -> bool:
    return inspector.has_table(name)


revision = "0010_elections"
down_revision = "0009_two_factor_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "elections"):
        op.create_table(
            "elections",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
            sa.Column("opens_at", sa.DateTime(), nullable=True),
            sa.Column("closes_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    _ensure_index(inspector, "elections", "ix_elections_status", ["status"])
    _ensure_index(inspector, "elections", "ix_elections_opens_at", ["opens_at"])
    _ensure_index(inspector, "elections", "ix_elections_closes_at", ["closes_at"])

    if not _has_table(inspector, "election_candidates"):
        op.create_table(
            "election_candidates",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id"), nullable=True),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("statement", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    _ensure_index(inspector, "election_candidates", "ix_election_candidates_election_id", ["election_id"])

    if not _has_table(inspector, "election_ballots"):
        op.create_table(
            "election_ballots",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token", sa.String(length=128), nullable=False, unique=True),
            sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("voted_at", sa.DateTime(), nullable=True),
            sa.Column("invalidated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("election_id", "owner_id", name="uq_election_ballots_election_owner"),
        )

    if not _has_table(inspector, "election_votes"):
        op.create_table(
            "election_votes",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "candidate_id",
                sa.Integer(),
                sa.ForeignKey("election_candidates.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "ballot_id",
                sa.Integer(),
                sa.ForeignKey("election_ballots.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("write_in", sa.String(length=255), nullable=True),
            sa.UniqueConstraint("ballot_id", name="uq_election_votes_ballot"),
        )
    _ensure_index(inspector, "election_votes", "ix_election_votes_election_id", ["election_id"])
    _ensure_index(inspector, "election_votes", "ix_election_votes_candidate_id", ["candidate_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "election_votes"):
        op.drop_table("election_votes")
    if _has_table(inspector, "election_ballots"):
        op.drop_table("election_ballots")
    if _has_table(inspector, "election_candidates"):
        op.drop_table("election_candidates")
    if _has_table(inspector, "elections"):
        op.drop_table("elections")
