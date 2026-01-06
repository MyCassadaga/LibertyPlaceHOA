"""Add ARC reviews and decision notification tracking.

Revision ID: 0015_arc_reviews_and_notifications
Revises: 0014_merge_heads_vendor_payments
Create Date: 2025-03-12
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0015_arc_reviews_and_notifications"
down_revision = "0014_merge_heads_vendor_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    op.add_column("arc_requests", sa.Column("decision_notified_at", sa.DateTime(), nullable=True))
    op.add_column("arc_requests", sa.Column("decision_notified_status", sa.String(), nullable=True))

    op.create_table(
        "arc_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arc_request_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, default=datetime.now(timezone.utc)),
        sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.now(timezone.utc)),
        sa.ForeignKeyConstraint(["arc_request_id"], ["arc_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("arc_request_id", "reviewer_user_id", name="uq_arc_reviews_request_reviewer"),
    )
    op.create_index(op.f("ix_arc_reviews_id"), "arc_reviews", ["id"], unique=False)
    op.create_index("ix_arc_reviews_request", "arc_reviews", ["arc_request_id"], unique=False)

    templates_table = sa.table(
        "templates",
        sa.Column("name", sa.String()),
        sa.Column("type", sa.String()),
        sa.Column("subject", sa.String()),
        sa.Column("body", sa.Text()),
        sa.Column("is_archived", sa.Boolean()),
        sa.Column("created_by_user_id", sa.Integer()),
        sa.Column("updated_by_user_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        templates_table,
        [
            {
                "name": "ARC_REQUEST_PASSED",
                "type": "ARC_REQUEST",
                "subject": "ARC Request Approved — {{arc_request_reference}} ({{arc_property_address}})",
                "body": (
                    "Hello {{arc_request_requester_name}},\n\n"
                    "Your ARC request has been APPROVED.\n\n"
                    "Request: {{arc_request_reference}}\n"
                    "Submitted: {{arc_request_submitted_at}}\n"
                    "Property: {{arc_property_address}}\n"
                    "Project: {{arc_request_title}}\n"
                    "Type: {{arc_request_project_type}}\n"
                    "Description: {{arc_request_description}}\n\n"
                    "Decision: APPROVED\n"
                    "Decision date: {{arc_request_decision_at}}\n"
                    "Conditions: {{arc_request_conditions}}\n"
                    "Attachments: {{arc_request_attachments}}\n\n"
                    "Next steps: You may proceed subject to any conditions above.\n\n"
                    "View your request: {{arc_request_portal_url}}\n"
                ),
                "is_archived": False,
                "created_by_user_id": None,
                "updated_by_user_id": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "ARC_REQUEST_FAILED",
                "type": "ARC_REQUEST",
                "subject": "ARC Request Not Approved — {{arc_request_reference}} ({{arc_property_address}})",
                "body": (
                    "Hello {{arc_request_requester_name}},\n\n"
                    "Your ARC request was NOT APPROVED at this time.\n\n"
                    "Request: {{arc_request_reference}}\n"
                    "Submitted: {{arc_request_submitted_at}}\n"
                    "Property: {{arc_property_address}}\n"
                    "Project: {{arc_request_title}}\n"
                    "Type: {{arc_request_project_type}}\n"
                    "Description: {{arc_request_description}}\n\n"
                    "Decision: NOT APPROVED\n"
                    "Decision date: {{arc_request_decision_at}}\n"
                    "Conditions: {{arc_request_conditions}}\n"
                    "Attachments: {{arc_request_attachments}}\n\n"
                    "We encourage you to review any reviewer comments in the portal and resubmit if desired. "
                    "If you have questions, please contact the board.\n\n"
                    "View your request: {{arc_request_portal_url}}\n"
                ),
                "is_archived": False,
                "created_by_user_id": None,
                "updated_by_user_id": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM templates WHERE name IN ('ARC_REQUEST_PASSED', 'ARC_REQUEST_FAILED') "
            "AND type = 'ARC_REQUEST'"
        )
    )
    op.drop_index("ix_arc_reviews_request", table_name="arc_reviews")
    op.drop_index(op.f("ix_arc_reviews_id"), table_name="arc_reviews")
    op.drop_table("arc_reviews")
    op.drop_column("arc_requests", "decision_notified_status")
    op.drop_column("arc_requests", "decision_notified_at")
