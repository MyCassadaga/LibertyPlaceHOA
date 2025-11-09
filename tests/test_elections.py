from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import Election, ElectionCandidate, ElectionBallot, OwnerUserLink
from backend.services.elections import compute_results, generate_ballots, record_vote


def _create_election(db_session, creator, status="OPEN") -> Election:
    election = Election(
        title="2026 Board Election",
        description="Annual board seats",
        status=status,
        opens_at=datetime.utcnow() - timedelta(days=1),
        closes_at=datetime.utcnow() + timedelta(days=7),
        created_by_user_id=creator.id,
    )
    db_session.add(election)
    db_session.commit()
    db_session.refresh(election)
    return election


def test_generate_ballots_and_vote(db_session, create_user, create_owner):
    manager = create_user(email="manager@example.com", role_name="SYSADMIN")
    election = _create_election(db_session, manager)

    candidate_owner = create_owner(name="Candidate Owner", email="candidate@example.com")
    candidate = ElectionCandidate(
        election_id=election.id,
        owner_id=candidate_owner.id,
        display_name="Candidate Smith",
    )
    db_session.add(candidate)
    db_session.commit()

    owner_one = create_owner(name="Owner One", email="one@example.com")
    owner_two = create_owner(name="Owner Two", email="two@example.com")

    created_ballots = generate_ballots(db_session, election, owners=[owner_one, owner_two])
    assert len(created_ballots) == 2
    assert all(isinstance(ballot.token, str) and len(ballot.token) > 10 for ballot in created_ballots)

    ballot_one = db_session.query(ElectionBallot).filter_by(owner_id=owner_one.id).one()
    record_vote(db_session, election, ballot_one, candidate, None)
    db_session.commit()

    results = compute_results(db_session, election)
    candidate_result = next((item for item in results if item["candidate_id"] == candidate.id), None)
    assert candidate_result is not None
    assert candidate_result["vote_count"] == 1


def test_record_vote_rejects_reuse(db_session, create_user, create_owner):
    manager = create_user(email="manager2@example.com", role_name="SYSADMIN")
    election = _create_election(db_session, manager)
    candidate = ElectionCandidate(
        election_id=election.id,
        display_name="Candidate One",
    )
    db_session.add(candidate)
    db_session.commit()

    owner = create_owner(name="Owner", email="owner@example.com")
    ballots = generate_ballots(db_session, election, owners=[owner])
    ballot = ballots[0]
    record_vote(db_session, election, ballot, candidate, None)
    db_session.commit()

    with pytest.raises(ValueError):
        record_vote(db_session, election, ballot, candidate, None)


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


def test_authenticated_vote_endpoint(db_session, create_user, create_owner):
    manager = create_user(email="manager-open@example.com", role_name="SYSADMIN")
    election = _create_election(db_session, manager)
    candidate_owner = create_owner(name="Candidate", email="candidate2@example.com")
    candidate = ElectionCandidate(
        election_id=election.id,
        owner_id=candidate_owner.id,
        display_name="Candidate Taylor",
    )
    db_session.add(candidate)
    db_session.commit()

    homeowner = create_owner(name="Voting Owner", email="vote@example.com")
    homeowner_user = create_user(email="vote@example.com", role_name="HOMEOWNER")
    db_session.add(OwnerUserLink(owner_id=homeowner.id, user_id=homeowner_user.id, link_type="PRIMARY"))
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner_user)
    client = TestClient(app)
    try:
        response = client.post(
            f"/elections/{election.id}/vote",
            json={"candidate_id": candidate.id},
        )
        assert response.status_code == 201
        assert response.json()["message"] == "Vote recorded."

        ballot = (
            db_session.query(ElectionBallot)
            .filter(ElectionBallot.election_id == election.id, ElectionBallot.owner_id == homeowner.id)
            .first()
        )
        assert ballot is not None
        assert ballot.voted_at is not None

        detail = client.get(f"/elections/{election.id}")
        assert detail.status_code == 200
        meta = detail.json().get("my_status")
        assert meta is not None
        assert meta["has_voted"] is True

        repeat = client.post(
            f"/elections/{election.id}/vote",
            json={"candidate_id": candidate.id},
        )
        assert repeat.status_code == 400
    finally:
        client.close()
        app.dependency_overrides.clear()
