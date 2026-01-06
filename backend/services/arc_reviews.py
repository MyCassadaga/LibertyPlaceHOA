from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from ..models.models import ARCRequest, ARCReview, Role, Template, User, user_roles
from ..services import email as email_service
from ..services.arc import transition_arc_request
from ..services.templates import build_arc_merge_context, render_template

logger = logging.getLogger(__name__)

ARC_REVIEW_DECISIONS = {"PASS", "FAIL"}


def calculate_review_status(eligible_count: int, pass_count: int, fail_count: int) -> str:
    if eligible_count <= 0:
        return "IN_REVIEW"
    pass_threshold = math.ceil(eligible_count / 2)
    fail_threshold = math.floor(eligible_count / 2) + 1
    if pass_count >= pass_threshold:
        return "PASSED"
    if fail_count >= fail_threshold:
        return "FAILED"
    return "IN_REVIEW"


def get_eligible_reviewer_ids(session: Session) -> List[int]:
    rows = (
        session.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(Role.name.in_(["ARC", "BOARD"]), User.is_active.is_(True))
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def get_eligible_reviewers(session: Session) -> List[User]:
    return (
        session.query(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(Role.name.in_(["ARC", "BOARD"]), User.is_active.is_(True))
        .distinct()
        .order_by(User.full_name, User.email)
        .all()
    )


def submit_review(
    *,
    session: Session,
    arc_request: ARCRequest,
    reviewer: User,
    decision: str,
    notes: str | None,
) -> ARCRequest:
    normalized = decision.strip().upper()
    if normalized not in ARC_REVIEW_DECISIONS:
        raise ValueError("Decision must be PASS or FAIL.")
    if arc_request.status in {"PASSED", "FAILED"}:
        raise ValueError("ARC request review is already finalized.")
    if arc_request.status not in {"SUBMITTED", "IN_REVIEW"}:
        raise ValueError("ARC request must be submitted before reviews can be recorded.")

    eligible_ids = get_eligible_reviewer_ids(session)
    if reviewer.id not in eligible_ids:
        raise ValueError("Reviewer is not eligible for this request.")

    if arc_request.status == "SUBMITTED":
        transition_arc_request(
            session=session,
            arc_request=arc_request,
            actor=reviewer,
            target_status="IN_REVIEW",
            reviewer_user_id=reviewer.id,
        )

    review = (
        session.query(ARCReview)
        .filter(ARCReview.arc_request_id == arc_request.id, ARCReview.reviewer_user_id == reviewer.id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if review:
        review.decision = normalized
        review.notes = notes
        review.submitted_at = now
    else:
        review = ARCReview(
            arc_request_id=arc_request.id,
            reviewer_user_id=reviewer.id,
            decision=normalized,
            notes=notes,
            submitted_at=now,
        )
        session.add(review)

    session.flush()

    pass_count = (
        session.query(ARCReview)
        .filter(ARCReview.arc_request_id == arc_request.id, ARCReview.decision == "PASS")
        .count()
    )
    fail_count = (
        session.query(ARCReview)
        .filter(ARCReview.arc_request_id == arc_request.id, ARCReview.decision == "FAIL")
        .count()
    )
    new_status = calculate_review_status(len(eligible_ids), pass_count, fail_count)
    if new_status in {"PASSED", "FAILED"} and arc_request.status != new_status:
        arc_request.status = new_status
        arc_request.final_decision_at = now
        arc_request.final_decision_by_user_id = reviewer.id
        session.add(arc_request)
    session.flush()
    return arc_request


def _resolve_template(session: Session, status: str) -> Template | None:
    template_name = "ARC_REQUEST_PASSED" if status == "PASSED" else "ARC_REQUEST_FAILED"
    return (
        session.query(Template)
        .filter(
            Template.name == template_name,
            Template.type == "ARC_REQUEST",
            Template.is_archived.is_(False),
        )
        .first()
    )


def maybe_send_decision_notification(session: Session, arc_request: ARCRequest) -> bool:
    if arc_request.status not in {"PASSED", "FAILED"}:
        return False
    if arc_request.decision_notified_status == arc_request.status and arc_request.decision_notified_at:
        return False

    recipient = None
    if arc_request.applicant and arc_request.applicant.email:
        recipient = arc_request.applicant.email
    elif arc_request.owner and arc_request.owner.primary_email:
        recipient = arc_request.owner.primary_email

    if not recipient:
        logger.warning("ARC decision notification skipped: no recipient for request %s", arc_request.id)
        return False

    template = _resolve_template(session, arc_request.status)
    if not template:
        logger.warning(
            "ARC decision notification skipped: template missing for status %s (request %s).",
            arc_request.status,
            arc_request.id,
        )
        return False

    context = build_arc_merge_context(
        arc_request=arc_request,
        owner=arc_request.owner,
        requester=arc_request.applicant,
    )
    rendered = render_template(template.subject, template.body, context)
    try:
        email_service.send_custom_email(rendered["subject"], rendered["body"], [recipient])
    except Exception:
        logger.exception("ARC decision email failed for request %s.", arc_request.id)
        return False

    arc_request.decision_notified_at = datetime.now(timezone.utc)
    arc_request.decision_notified_status = arc_request.status
    session.add(arc_request)
    session.commit()
    return True
