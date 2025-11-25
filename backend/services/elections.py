from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import (
    Election,
    ElectionBallot,
    ElectionCandidate,
    ElectionVote,
    Owner,
)


def generate_ballots(session: Session, election: Election, owners: Optional[Iterable[Owner]] = None) -> list[ElectionBallot]:
    """Create ballots (with tokens) for all provided owners, skipping existing ones."""
    if owners is None:
        owners = (
            session.query(Owner)
            .filter(Owner.is_archived.is_(False))
            .order_by(Owner.id.asc())
            .all()
        )

    created: list[ElectionBallot] = []
    existing_by_owner = {
        ballot.owner_id: ballot
        for ballot in election.ballots
    }

    for owner in owners:
        ballot = existing_by_owner.get(owner.id)
        if ballot and ballot.token:
            continue

        token = secrets.token_urlsafe(24)
        if ballot:
            ballot.token = token
            ballot.issued_at = datetime.now(timezone.utc)
            ballot.invalidated_at = None
            ballot.voted_at = None
        else:
            ballot = ElectionBallot(
                election_id=election.id,
                owner_id=owner.id,
                token=token,
            )
            session.add(ballot)
            election.ballots.append(ballot)
        created.append(ballot)

    session.flush()
    return created


def compute_results(session: Session, election: Election, include_write_ins: bool = True) -> list[dict[str, object]]:
    """Return aggregated vote counts for an election."""
    rows = (
        session.query(
            ElectionCandidate.id.label("candidate_id"),
            ElectionCandidate.display_name.label("candidate_name"),
            func.count(ElectionVote.id).label("vote_count"),
        )
        .outerjoin(ElectionVote, ElectionVote.candidate_id == ElectionCandidate.id)
        .filter(ElectionCandidate.election_id == election.id)
        .group_by(ElectionCandidate.id)
        .order_by(func.count(ElectionVote.id).desc(), ElectionCandidate.display_name.asc())
        .all()
    )
    results = [
        {
            "candidate_id": row.candidate_id,
            "candidate_name": row.candidate_name,
            "vote_count": int(row.vote_count),
        }
        for row in rows
    ]
    if include_write_ins:
        write_in_total = (
            session.query(func.count(ElectionVote.id))
            .filter(
                ElectionVote.election_id == election.id,
                ElectionVote.candidate_id.is_(None),
                ElectionVote.write_in.isnot(None),
            )
            .scalar()
        ) or 0
        if write_in_total > 0:
            results.append(
                {
                    "candidate_id": None,
                    "candidate_name": "Write-in",
                    "vote_count": int(write_in_total),
                }
            )
    return results


def calculate_election_stats(session: Session, election: Election) -> dict[str, object]:
    """Compute turnout metrics and aggregated results for the supplied election."""
    ballot_count = len(election.ballots)
    votes_cast = sum(1 for ballot in election.ballots if ballot.voted_at is not None)
    abstentions = max(ballot_count - votes_cast, 0)
    turnout_percent = float(round((votes_cast / ballot_count * 100) if ballot_count else 0.0, 2))
    results = compute_results(session, election, include_write_ins=True)
    write_in_entry = next((row for row in results if row["candidate_id"] is None and row["candidate_name"] == "Write-in"), None)
    write_in_count = int(write_in_entry["vote_count"]) if write_in_entry else 0

    return {
        "election_id": election.id,
        "ballot_count": ballot_count,
        "votes_cast": votes_cast,
        "turnout_percent": turnout_percent,
        "abstentions": abstentions,
        "write_in_count": write_in_count,
        "results": results,
    }


def record_vote(
    session: Session,
    election: Election,
    ballot: ElectionBallot,
    candidate: Optional[ElectionCandidate],
    write_in: Optional[str] = None,
) -> ElectionVote:
    """Persist a vote for the supplied ballot."""
    if ballot.voted_at is not None:
        raise ValueError("Ballot has already been used.")
    if ballot.invalidated_at is not None:
        raise ValueError("Ballot has been invalidated.")

    vote = ElectionVote(
        election_id=election.id,
        candidate_id=candidate.id if candidate else None,
        ballot_id=ballot.id,
        write_in=write_in.strip() if write_in else None,
    )
    ballot.voted_at = datetime.now(timezone.utc)
    session.add(vote)
    session.flush()
    return vote


def get_or_create_owner_ballot(session: Session, election: Election, owner: Owner) -> ElectionBallot:
    ballot = (
        session.query(ElectionBallot)
        .filter(ElectionBallot.election_id == election.id, ElectionBallot.owner_id == owner.id)
        .first()
    )
    if ballot:
        return ballot
    token = secrets.token_urlsafe(24)
    ballot = ElectionBallot(
        election_id=election.id,
        owner_id=owner.id,
        token=token,
    )
    session.add(ballot)
    session.flush()
    return ballot
