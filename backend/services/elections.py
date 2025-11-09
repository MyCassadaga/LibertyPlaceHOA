from __future__ import annotations

import secrets
from datetime import datetime
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
            ballot.issued_at = datetime.utcnow()
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


def compute_results(session: Session, election: Election) -> list[dict[str, object]]:
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
    return [
        {
            "candidate_id": row.candidate_id,
            "candidate_name": row.candidate_name,
            "vote_count": int(row.vote_count),
        }
        for row in rows
    ]


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
    ballot.voted_at = datetime.utcnow()
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
