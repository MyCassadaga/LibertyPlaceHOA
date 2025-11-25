import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db, get_owner_for_user
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Election, ElectionBallot, ElectionCandidate, Owner, User
from ..schemas.schemas import (
    ElectionAdminBallotRead,
    ElectionAuthenticatedVote,
    ElectionCandidateCreate,
    ElectionCandidateRead,
    ElectionCreate,
    ElectionListItem,
    ElectionMyStatus,
    ElectionPublicRead,
    ElectionRead,
    ElectionResultRead,
    ElectionStatsRead,
    ElectionUpdate,
    ElectionVoteCast,
)
from ..services.elections import (
    calculate_election_stats,
    compute_results,
    generate_ballots,
    get_or_create_owner_ballot,
    record_vote,
)
from ..services.notifications import create_notification

router = APIRouter()


def _load_election(db: Session, election_id: int) -> Election:
    election = db.get(
        Election,
        election_id,
        options=[
            joinedload(Election.candidates),
            joinedload(Election.ballots),
            joinedload(Election.votes),
        ],
    )
    if not election:
        raise HTTPException(status_code=404, detail="Election not found.")
    return election


def _summarize_election(
    election: Election,
    include_results: bool,
    db: Session,
    owner: Optional[Owner] = None,
) -> ElectionRead:
    results: List[Dict[str, object]] = []
    if include_results or election.status.upper() in {"CLOSED", "ARCHIVED"}:
        results = compute_results(db, election)

    issued_ballots = len(election.ballots)
    votes_cast = sum(1 for ballot in election.ballots if ballot.voted_at is not None)

    my_status: Optional[ElectionMyStatus] = None
    if owner:
        ballot = next((entry for entry in election.ballots if entry.owner_id == owner.id), None)
        my_status = ElectionMyStatus(
            has_ballot=ballot is not None,
            has_voted=bool(ballot and ballot.voted_at),
            voted_at=ballot.voted_at if ballot and ballot.voted_at else None,
        )

    return ElectionRead(
        id=election.id,
        title=election.title,
        description=election.description,
        status=election.status,
        opens_at=election.opens_at,
        closes_at=election.closes_at,
        created_at=election.created_at,
        updated_at=election.updated_at,
        candidates=[ElectionCandidateRead.from_orm(candidate) for candidate in election.candidates],
        ballot_count=issued_ballots,
        votes_cast=votes_cast,
        results=[ElectionResultRead(**result) for result in results],
        my_status=my_status,
    )


@router.get("/", response_model=List[ElectionListItem])
def list_elections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
) -> List[ElectionListItem]:
    query = (
        db.query(Election)
        .options(joinedload(Election.candidates), joinedload(Election.ballots))
        .order_by(Election.opens_at.asc().nullsfirst())
    )
    manager_roles = {"BOARD", "SYSADMIN", "SECRETARY", "TREASURER", "ATTORNEY"}
    is_manager = user.has_any_role(*manager_roles)

    if not is_manager:
        # Homeowners only see scheduled/open elections
        query = query.filter(Election.status.in_(["OPEN", "SCHEDULED"]))
    elif not include_archived:
        query = query.filter(Election.status != "ARCHIVED")

    elections = query.all()
    items: List[ElectionListItem] = []
    for election in elections:
        total_ballots = len(election.ballots)
        votes_cast = sum(1 for ballot in election.ballots if ballot.voted_at is not None)
        items.append(
            ElectionListItem(
                id=election.id,
                title=election.title,
                status=election.status,
                opens_at=election.opens_at,
                closes_at=election.closes_at,
                ballot_count=total_ballots,
                votes_cast=votes_cast,
            )
        )
    return items


@router.post("/", response_model=ElectionRead, status_code=status.HTTP_201_CREATED)
def create_election(
    payload: ElectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> Election:
    election = Election(
        title=payload.title,
        description=payload.description,
        status=payload.status or "DRAFT",
        opens_at=payload.opens_at,
        closes_at=payload.closes_at,
        created_by_user_id=user.id,
    )
    db.add(election)
    db.commit()
    db.refresh(election)
    return _summarize_election(election, include_results=False, db=db)


@router.patch("/{election_id}", response_model=ElectionRead)
def update_election(
    election_id: int,
    payload: ElectionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> Election:
    election = _load_election(db, election_id)
    previous_status = election.status
    updates = payload.dict(exclude_unset=True)
    if not updates:
        return _summarize_election(election, include_results=True, db=db)

    for field, value in updates.items():
        setattr(election, field, value)
    election.updated_at = datetime.now(timezone.utc)
    db.add(election)
    db.commit()
    db.refresh(election)

    status_changed_to = updates.get("status")
    if status_changed_to and status_changed_to != previous_status:
        notifications_created = []
        if status_changed_to == "OPEN":
            notifications_created = create_notification(
                db,
                title=f"{election.title} is now open",
                message="Your community election is open for voting. Cast your ballot before it closes.",
                level="info",
                link_url="/elections",
                role_names=["HOMEOWNER"],
            )
        elif status_changed_to == "SCHEDULED":
            notifications_created = create_notification(
                db,
                title=f"{election.title} scheduled",
                message="An upcoming election has been scheduled. Review the details and candidates.",
                level="info",
                link_url="/elections",
                role_names=["BOARD", "SYSADMIN", "SECRETARY"],
            )
        elif status_changed_to == "CLOSED":
            notifications_created = create_notification(
                db,
                title=f"{election.title} closed",
                message="Voting has closed for the election. Results will be posted shortly.",
                level="info",
                link_url="/elections",
                role_names=["BOARD", "SYSADMIN", "SECRETARY"],
            )
        if notifications_created:
            db.commit()

    return _summarize_election(election, include_results=True, db=db)


@router.post("/{election_id}/candidates", response_model=ElectionCandidateRead, status_code=status.HTTP_201_CREATED)
def add_candidate(
    election_id: int,
    payload: ElectionCandidateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> ElectionCandidate:
    election = _load_election(db, election_id)
    candidate = ElectionCandidate(
        election_id=election.id,
        owner_id=payload.owner_id,
        display_name=payload.display_name,
        statement=payload.statement,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return ElectionCandidateRead.from_orm(candidate)


@router.delete("/{election_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_candidate(
    election_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> None:
    candidate = (
        db.query(ElectionCandidate)
        .filter(ElectionCandidate.id == candidate_id, ElectionCandidate.election_id == election_id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    db.delete(candidate)
    db.commit()


@router.post("/{election_id}/ballots/generate", response_model=List[ElectionAdminBallotRead])
def generate_election_ballots(
    election_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> List[ElectionAdminBallotRead]:
    election = _load_election(db, election_id)
    created = generate_ballots(db, election)
    db.commit()
    db.refresh(election)

    owners = {ballot.owner_id: db.get(Owner, ballot.owner_id) for ballot in election.ballots}
    results: List[ElectionAdminBallotRead] = []
    for ballot in election.ballots:
        owner = owners.get(ballot.owner_id)
        results.append(
            ElectionAdminBallotRead(
                id=ballot.id,
                owner_id=ballot.owner_id,
                owner_name=owner.primary_name if owner else None,
                token=ballot.token,
                issued_at=ballot.issued_at,
                voted_at=ballot.voted_at,
            )
        )
    return results


@router.get("/{election_id}/ballots", response_model=List[ElectionAdminBallotRead])
def list_ballots(
    election_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY")),
) -> List[ElectionAdminBallotRead]:
    election = _load_election(db, election_id)
    owners = {ballot.owner_id: db.get(Owner, ballot.owner_id) for ballot in election.ballots}
    return [
        ElectionAdminBallotRead(
            id=ballot.id,
            owner_id=ballot.owner_id,
            owner_name=owners.get(ballot.owner_id).primary_name if owners.get(ballot.owner_id) else None,
            token=ballot.token,
            issued_at=ballot.issued_at,
            voted_at=ballot.voted_at,
        )
        for ballot in election.ballots
    ]


@router.get("/{election_id}", response_model=ElectionRead)
def get_election(
    election_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Election:
    election = _load_election(db, election_id)
    manager_roles = {"BOARD", "SYSADMIN", "SECRETARY", "TREASURER", "ATTORNEY"}
    include_results = user.has_any_role(*manager_roles)
    owner = get_owner_for_user(db, user)
    return _summarize_election(election, include_results=include_results, db=db, owner=owner)


@router.get("/{election_id}/stats", response_model=ElectionStatsRead)
def get_election_stats(
    election_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY", "TREASURER", "ATTORNEY")),
) -> ElectionStatsRead:
    election = _load_election(db, election_id)
    stats = calculate_election_stats(db, election)
    return ElectionStatsRead(**stats)


@router.get("/{election_id}/results.csv")
def download_election_results_csv(
    election_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "SYSADMIN", "SECRETARY", "TREASURER", "ATTORNEY")),
) -> StreamingResponse:
    election = _load_election(db, election_id)
    stats = calculate_election_stats(db, election)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Election", election.title])
    writer.writerow(["Status", election.status])
    writer.writerow(["Ballots issued", stats["ballot_count"]])
    writer.writerow(["Votes cast", stats["votes_cast"]])
    writer.writerow(["Turnout %", f'{stats["turnout_percent"]:.2f}'])
    writer.writerow(["Abstentions", stats["abstentions"]])
    writer.writerow(["Write-in votes", stats["write_in_count"]])
    writer.writerow([])
    writer.writerow(["Candidate", "Votes", "% of votes"])
    total_votes = stats["votes_cast"] or 0
    for result in stats["results"]:
        percent = (result["vote_count"] / total_votes * 100) if total_votes else 0.0
        candidate_name = result["candidate_name"] or "Write-in"
        writer.writerow([candidate_name, result["vote_count"], f"{percent:.2f}%"])
    if stats["abstentions"]:
        abstain_percent = (stats["abstentions"] / stats["ballot_count"] * 100) if stats["ballot_count"] else 0.0
        writer.writerow(["Abstentions (no vote recorded)", stats["abstentions"], f"{abstain_percent:.2f}%"])

    buffer.seek(0)
    filename = f"election-{election.id}-results.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/public/{election_id}", response_model=ElectionPublicRead)
def get_public_election(
    election_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> ElectionPublicRead:
    election = _load_election(db, election_id)
    if election.status.upper() != "OPEN":
        raise HTTPException(status_code=400, detail="Election is not open for voting.")

    ballot = (
        db.query(ElectionBallot)
        .filter(ElectionBallot.election_id == election.id, ElectionBallot.token == token)
        .first()
    )
    if not ballot:
        raise HTTPException(status_code=404, detail="Invalid or expired ballot token.")
    if ballot.invalidated_at is not None:
        raise HTTPException(status_code=400, detail="Ballot has been invalidated.")

    return ElectionPublicRead(
        id=election.id,
        title=election.title,
        description=election.description,
        status=election.status,
        opens_at=election.opens_at,
        closes_at=election.closes_at,
        candidates=[ElectionCandidateRead.from_orm(candidate) for candidate in election.candidates],
        has_voted=ballot.voted_at is not None,
    )


@router.post("/public/{election_id}/vote", status_code=status.HTTP_201_CREATED)
def cast_public_vote(
    election_id: int,
    payload: ElectionVoteCast,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    election = _load_election(db, election_id)
    if election.status.upper() != "OPEN":
        raise HTTPException(status_code=400, detail="Election is not open for voting.")

    ballot = (
        db.query(ElectionBallot)
        .filter(ElectionBallot.election_id == election.id, ElectionBallot.token == payload.token)
        .first()
    )
    if not ballot:
        raise HTTPException(status_code=404, detail="Invalid or expired ballot token.")
    if ballot.invalidated_at is not None:
        raise HTTPException(status_code=400, detail="Ballot has been invalidated.")
    if ballot.voted_at is not None:
        raise HTTPException(status_code=400, detail="Ballot has already been used.")

    candidate = None
    if payload.candidate_id is not None:
        candidate = (
            db.query(ElectionCandidate)
            .filter(ElectionCandidate.id == payload.candidate_id, ElectionCandidate.election_id == election.id)
            .first()
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found for this election.")

    record_vote(db, election, ballot, candidate, payload.write_in)
    db.commit()
    return {"message": "Vote recorded."}


@router.post("/{election_id}/vote", status_code=status.HTTP_201_CREATED)
def cast_authenticated_vote(
    election_id: int,
    payload: ElectionAuthenticatedVote,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    election = _load_election(db, election_id)
    if election.status.upper() != "OPEN":
        raise HTTPException(status_code=400, detail="Election is not open for voting.")

    owner = get_owner_for_user(db, user)
    if not owner or owner.is_archived:
        raise HTTPException(status_code=403, detail="Voting is limited to active homeowner accounts.")

    ballot = get_or_create_owner_ballot(db, election, owner)
    if ballot.voted_at is not None:
        raise HTTPException(status_code=400, detail="You have already voted in this election.")

    if payload.candidate_id is None and not (payload.write_in and payload.write_in.strip()):
        raise HTTPException(status_code=400, detail="Select a candidate or provide a write-in.")

    candidate = None
    if payload.candidate_id is not None:
        candidate = (
            db.query(ElectionCandidate)
            .filter(ElectionCandidate.id == payload.candidate_id, ElectionCandidate.election_id == election.id)
            .first()
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found for this election.")

    record_vote(db, election, ballot, candidate, payload.write_in)
    db.commit()
    return {"message": "Vote recorded."}
