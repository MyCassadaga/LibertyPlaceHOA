import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import ARCRequest, AuditLog, OwnerUserLink
from backend.services.arc import transition_arc_request


def _override_get_db(session):
    def _generator():
        try:
            yield session
        finally:
            pass

    return _generator


def _override_user(user):
    def _provider():
        return user

    return _provider


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


def test_homeowner_cannot_submit_for_unlinked_address(db_session, create_user, create_owner):
    homeowner = create_user(email="homeowner@example.com", role_name="HOMEOWNER")
    owner = create_owner(name="Linked", email="linked@example.com")
    other_owner = create_owner(name="Other", email="other@example.com")
    db_session.add(OwnerUserLink(owner_id=owner.id, user_id=homeowner.id, link_type="PRIMARY"))
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    client = TestClient(app)
    try:
        response = client.post(
            "/arc/requests",
            json={
                "title": "Garage update",
                "project_type": "Exterior",
                "description": "Paint change",
                "owner_id": other_owner.id,
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not permitted to submit for this address."
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_homeowner_requires_owner_id_with_multiple_addresses(db_session, create_user, create_owner):
    homeowner = create_user(email="multi@example.com", role_name="HOMEOWNER")
    owner_one = create_owner(name="Linked One", email="multi@example.com")
    owner_two = create_owner(name="Linked Two", email="multi@example.com")
    db_session.add_all(
        [
            OwnerUserLink(owner_id=owner_one.id, user_id=homeowner.id, link_type="PRIMARY"),
            OwnerUserLink(owner_id=owner_two.id, user_id=homeowner.id, link_type="SECONDARY"),
        ]
    )
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    client = TestClient(app)
    try:
        response = client.post(
            "/arc/requests",
            json={
                "title": "Fence update",
                "project_type": "Fence",
                "description": "Replace fence",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "owner_id is required for homeowners with multiple addresses."
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_list_linked_owners_returns_only_associated_addresses(db_session, create_user, create_owner):
    homeowner = create_user(email="linked@example.com", role_name="HOMEOWNER")
    owner_one = create_owner(name="Linked Owner", email="linked@example.com")
    owner_two = create_owner(name="Linked Owner Two", email="linked@example.com")
    other_owner = create_owner(name="Other Owner", email="other@example.com")
    db_session.add_all(
        [
            OwnerUserLink(owner_id=owner_one.id, user_id=homeowner.id, link_type="PRIMARY"),
            OwnerUserLink(owner_id=owner_two.id, user_id=homeowner.id, link_type="SECONDARY"),
        ]
    )
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    client = TestClient(app)
    try:
        response = client.get("/owners/linked")
        assert response.status_code == 200
        payload = response.json()
        ids = {owner["id"] for owner in payload}
        assert owner_one.id in ids
        assert owner_two.id in ids
        assert other_owner.id not in ids
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_homeowner_get_returns_only_their_requests(db_session, create_user, create_owner):
    homeowner = create_user(email="ownerlist@example.com", role_name="HOMEOWNER")
    owner_one = create_owner(name="Linked One", email="ownerlist@example.com")
    owner_two = create_owner(name="Linked Two", email="ownerlist@example.com")
    other_owner = create_owner(name="Other", email="other@example.com")
    db_session.add_all(
        [
            OwnerUserLink(owner_id=owner_one.id, user_id=homeowner.id, link_type="PRIMARY"),
            OwnerUserLink(owner_id=owner_two.id, user_id=homeowner.id, link_type="SECONDARY"),
        ]
    )
    db_session.commit()

    _create_arc_request(db_session, owner_one, homeowner)
    _create_arc_request(db_session, owner_two, homeowner)
    _create_arc_request(db_session, other_owner, homeowner)

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    client = TestClient(app)
    try:
        response = client.get("/arc/requests")
        assert response.status_code == 200
        payload = response.json()
        owner_ids = {item["owner_id"] for item in payload}
        assert owner_one.id in owner_ids
        assert owner_two.id in owner_ids
        assert other_owner.id not in owner_ids
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_board_get_returns_all_requests(db_session, create_user, create_owner):
    board_member = create_user(email="board@example.com", role_name="BOARD")
    owner_one = create_owner(name="Owner One", email="board1@example.com")
    owner_two = create_owner(name="Owner Two", email="board2@example.com")
    owner_three = create_owner(name="Owner Three", email="board3@example.com")

    _create_arc_request(db_session, owner_one, board_member)
    _create_arc_request(db_session, owner_two, board_member)
    _create_arc_request(db_session, owner_three, board_member)

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_member)
    client = TestClient(app)
    try:
        response = client.get("/arc/requests")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 3
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_homeowner_post_with_linked_address_succeeds(db_session, create_user, create_owner):
    homeowner = create_user(email="allowpost@example.com", role_name="HOMEOWNER")
    owner = create_owner(name="Linked", email="allowpost@example.com")
    db_session.add(OwnerUserLink(owner_id=owner.id, user_id=homeowner.id, link_type="PRIMARY"))
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    client = TestClient(app)
    try:
        response = client.post(
            "/arc/requests",
            json={
                "title": "Driveway update",
                "project_type": "Exterior",
                "description": "Expand driveway",
                "owner_id": owner.id,
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["owner_id"] == owner.id
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_arc_requests_missing_auth_returns_401():
    client = TestClient(app)
    try:
        response = client.get("/arc/requests")
        assert response.status_code == 401
    finally:
        client.close()


def test_arc_request_bad_payload_returns_422(db_session, create_user, create_owner):
    board_member = create_user(email="badpayload@example.com", role_name="BOARD")
    owner = create_owner(name="Owner", email="badpayload@example.com")

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_member)
    client = TestClient(app)
    try:
        response = client.post(
            "/arc/requests",
            json={
                "title": " ",
                "project_type": "Exterior",
                "description": "Paint update",
                "owner_id": owner.id,
            },
        )
        assert response.status_code == 422
    finally:
        client.close()
        app.dependency_overrides.clear()
