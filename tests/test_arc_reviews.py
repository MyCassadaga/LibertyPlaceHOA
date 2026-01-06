import pytest

from backend.models.models import ARCRequest, Template
from backend.services import arc_reviews


@pytest.mark.parametrize(
    ("eligible", "pass_count", "fail_count", "expected"),
    [
        (3, 2, 0, "PASSED"),
        (3, 1, 2, "FAILED"),
        (4, 2, 0, "PASSED"),
        (4, 0, 3, "FAILED"),
        (4, 0, 2, "IN_REVIEW"),
        (5, 3, 0, "PASSED"),
        (6, 3, 0, "PASSED"),
    ],
)
def test_calculate_review_status(eligible, pass_count, fail_count, expected):
    assert arc_reviews.calculate_review_status(eligible, pass_count, fail_count) == expected


def test_arc_decision_notification_idempotent(db_session, create_owner, create_user, monkeypatch):
    applicant = create_user(email="requester@example.com", role_name="HOMEOWNER")
    owner = create_owner(email="owner@example.com")
    arc_request = ARCRequest(
        owner_id=owner.id,
        submitted_by_user_id=applicant.id,
        title="Fence update",
        description="Replace fence",
        status="PASSED",
    )
    db_session.add(arc_request)
    db_session.commit()

    db_session.add_all(
        [
            Template(
                name="ARC_REQUEST_PASSED",
                type="ARC_REQUEST",
                subject="Approved {{arc_request_reference}}",
                body="Decision {{arc_request_decision}}",
            ),
            Template(
                name="ARC_REQUEST_FAILED",
                type="ARC_REQUEST",
                subject="Denied {{arc_request_reference}}",
                body="Decision {{arc_request_decision}}",
            ),
        ]
    )
    db_session.commit()

    sent = {"count": 0}

    def _fake_send(subject, body, recipients, from_address=None, reply_to=None):
        sent["count"] += 1
        return recipients

    monkeypatch.setattr(arc_reviews.email_service, "send_custom_email", _fake_send)

    arc_request = db_session.get(ARCRequest, arc_request.id)
    assert arc_reviews.maybe_send_decision_notification(db_session, arc_request) is True
    arc_request = db_session.get(ARCRequest, arc_request.id)
    assert arc_request.decision_notified_status == "PASSED"
    assert arc_request.decision_notified_at is not None

    arc_request = db_session.get(ARCRequest, arc_request.id)
    assert arc_reviews.maybe_send_decision_notification(db_session, arc_request) is False
    assert sent["count"] == 1
