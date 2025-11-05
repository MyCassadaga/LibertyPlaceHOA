import pytest

from backend.models.models import ARCRequest, AuditLog
from backend.services.arc import transition_arc_request


def _create_arc_request(db_session, owner, applicant, status="SUBMITTED"):
    arc_request = ARCRequest(
        owner_id=owner.id,
        submitted_by_user_id=applicant.id,
        status=status,
        title="Deck Extension",
        description="Extend deck by 10 feet",
    )
    db_session.add(arc_request)
    db_session.commit()
    return arc_request


def test_arc_transition_updates_status_and_logs(db_session, create_user, create_owner):
    reviewer = create_user(email="reviewer@example.com", role_name="BOARD")
    owner = create_owner()
    arc_request = _create_arc_request(db_session, owner, reviewer, status="SUBMITTED")

    transition_arc_request(db_session, arc_request, reviewer, "IN_REVIEW", reviewer_user_id=reviewer.id)

    refreshed = db_session.query(ARCRequest).filter_by(id=arc_request.id).one()
    assert refreshed.status == "IN_REVIEW"
    assert refreshed.reviewer_user_id == reviewer.id

    audit_entry = db_session.query(AuditLog).filter(AuditLog.action == "arc.transition").one()
    assert '"status": "IN_REVIEW"' in (audit_entry.after or "")
    assert '"status": "SUBMITTED"' in (audit_entry.before or "")


def test_arc_transition_records_decision_metadata(db_session, create_user, create_owner):
    actor = create_user(role_name="SYSADMIN")
    owner = create_owner()
    arc_request = _create_arc_request(db_session, owner, actor, status="IN_REVIEW")

    transition_arc_request(
        db_session,
        arc_request,
        actor,
        "APPROVED",
        reviewer_user_id=actor.id,
        notes="All set",
    )

    refreshed = db_session.query(ARCRequest).filter_by(id=arc_request.id).one()
    assert refreshed.status == "APPROVED"
    assert refreshed.final_decision_at is not None
    assert refreshed.final_decision_by_user_id == actor.id
    assert refreshed.decision_notes == "All set"


def test_arc_transition_rejects_invalid_target(db_session, create_user, create_owner):
    actor = create_user(role_name="SYSADMIN")
    owner = create_owner()
    arc_request = _create_arc_request(db_session, owner, actor, status="SUBMITTED")

    with pytest.raises(ValueError):
        transition_arc_request(db_session, arc_request, actor, "APPROVED")
