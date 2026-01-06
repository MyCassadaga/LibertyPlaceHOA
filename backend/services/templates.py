from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

from ..models.models import ARCRequest, NoticeType, Owner, User, Violation
from ..config import settings

MERGE_TAGS: List[Dict[str, str]] = [
    {
        "key": "owner_name",
        "label": "Owner name",
        "description": "Primary owner full name.",
        "sample": "Taylor Jordan",
    },
    {
        "key": "owner_first_name",
        "label": "Owner first name",
        "description": "First name from the primary owner record.",
        "sample": "Taylor",
    },
    {
        "key": "owner_email",
        "label": "Owner email",
        "description": "Primary owner email address.",
        "sample": "taylor@example.com",
    },
    {
        "key": "owner_address",
        "label": "Owner address",
        "description": "Property address on the owner record.",
        "sample": "123 Liberty Place",
    },
    {
        "key": "owner_lot",
        "label": "Owner lot",
        "description": "Lot identifier for the owner.",
        "sample": "Lot 12",
    },
    {
        "key": "owner_balance",
        "label": "Owner balance",
        "description": "Outstanding balance (if provided).",
        "sample": "$245.00",
    },
    {
        "key": "violation_id",
        "label": "Violation ID",
        "description": "Violation case identifier.",
        "sample": "417",
    },
    {
        "key": "violation_category",
        "label": "Violation category",
        "description": "Category for the violation.",
        "sample": "Exterior Maintenance",
    },
    {
        "key": "violation_description",
        "label": "Violation description",
        "description": "Description entered for the violation.",
        "sample": "Fence boards need repainting.",
    },
    {
        "key": "violation_due_date",
        "label": "Violation due date",
        "description": "Date the violation should be resolved.",
        "sample": "2025-12-01",
    },
    {
        "key": "violation_hearing_date",
        "label": "Violation hearing date",
        "description": "Scheduled hearing date for the violation.",
        "sample": "2025-12-10",
    },
    {
        "key": "violation_fine_amount",
        "label": "Violation fine amount",
        "description": "Fine amount for the violation.",
        "sample": "$50.00",
    },
    {
        "key": "notice_type",
        "label": "Notice type",
        "description": "Notice type code.",
        "sample": "NEWSLETTER",
    },
    {
        "key": "actor_name",
        "label": "Staff name",
        "description": "Name or email for the staff user sending the notice.",
        "sample": "Jordan Smith",
    },
    {
        "key": "current_date",
        "label": "Current date",
        "description": "Date of message generation.",
        "sample": "2025-11-08",
    },
    {
        "key": "current_datetime",
        "label": "Current date & time",
        "description": "Date/time of message generation.",
        "sample": "2025-11-08 12:00 UTC",
    },
    {
        "key": "arc_request_reference",
        "label": "ARC request reference",
        "description": "ARC request identifier (ARC-123).",
        "sample": "ARC-123",
    },
    {
        "key": "arc_request_id",
        "label": "ARC request ID",
        "description": "ARC request database identifier.",
        "sample": "123",
    },
    {
        "key": "arc_request_title",
        "label": "ARC request title",
        "description": "Project title for the ARC request.",
        "sample": "Front yard fencing",
    },
    {
        "key": "arc_request_project_type",
        "label": "ARC request project type",
        "description": "Project type/category.",
        "sample": "Fence",
    },
    {
        "key": "arc_request_description",
        "label": "ARC request description",
        "description": "Project description.",
        "sample": "Replace fence with cedar slats.",
    },
    {
        "key": "arc_request_submitted_at",
        "label": "ARC request submitted date",
        "description": "Date/time of submission.",
        "sample": "2025-03-10 09:00 UTC",
    },
    {
        "key": "arc_request_decision_at",
        "label": "ARC request decision date",
        "description": "Date/time of the decision.",
        "sample": "2025-03-12 14:30 UTC",
    },
    {
        "key": "arc_request_decision",
        "label": "ARC request decision",
        "description": "Decision result text.",
        "sample": "APPROVED",
    },
    {
        "key": "arc_request_requester_name",
        "label": "ARC requester name",
        "description": "Name of the requester.",
        "sample": "Taylor Jordan",
    },
    {
        "key": "arc_request_requester_email",
        "label": "ARC requester email",
        "description": "Email of the requester.",
        "sample": "taylor@example.com",
    },
    {
        "key": "arc_property_address",
        "label": "ARC property address",
        "description": "Property address associated with the request.",
        "sample": "123 Liberty Place",
    },
    {
        "key": "arc_property_lot",
        "label": "ARC property lot",
        "description": "Lot identifier for the request.",
        "sample": "Lot 12",
    },
    {
        "key": "arc_request_conditions",
        "label": "ARC request conditions",
        "description": "Conditions attached to the decision.",
        "sample": "None",
    },
    {
        "key": "arc_request_attachments",
        "label": "ARC request attachments",
        "description": "Attachment list for the request.",
        "sample": "fence_plan.pdf",
    },
    {
        "key": "arc_request_portal_url",
        "label": "ARC request portal link",
        "description": "Portal URL for the request.",
        "sample": "https://portal.example.com/arc?requestId=123",
    },
]

TAG_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def merge_tag_definitions() -> List[Dict[str, str]]:
    return MERGE_TAGS


def sample_merge_context() -> Dict[str, str]:
    return {tag["key"]: tag["sample"] for tag in MERGE_TAGS}


def build_merge_context(
    *,
    owner: Optional[Owner] = None,
    violation: Optional[Violation] = None,
    notice_type: Optional[NoticeType] = None,
    actor: Optional[User] = None,
    owner_balance: Optional[str] = None,
    violation_fine_amount: Optional[str] = None,
) -> Dict[str, str]:
    now = datetime.now(timezone.utc)
    context = sample_merge_context()
    context.update(
        {
            "current_date": now.date().isoformat(),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M %Z"),
        }
    )
    if owner:
        context.update(
            {
                "owner_name": owner.primary_name,
                "owner_first_name": (owner.primary_name.split(" ")[0] if owner.primary_name else ""),
                "owner_email": owner.primary_email or "",
                "owner_address": owner.property_address or "",
                "owner_lot": owner.lot or "",
            }
        )
    if owner_balance is not None:
        context["owner_balance"] = owner_balance
    if violation:
        context.update(
            {
                "violation_id": str(violation.id),
                "violation_category": violation.category,
                "violation_description": violation.description or "",
                "violation_due_date": violation.due_date.isoformat() if violation.due_date else "",
                "violation_hearing_date": violation.hearing_date.isoformat() if violation.hearing_date else "",
                "violation_fine_amount": (
                    f"${violation.fine_amount:.2f}" if violation.fine_amount is not None else ""
                ),
            }
        )
    if violation_fine_amount is not None:
        context["violation_fine_amount"] = violation_fine_amount
    if notice_type:
        context["notice_type"] = notice_type.code
    if actor:
        context["actor_name"] = actor.full_name or actor.email
    return context


def build_arc_merge_context(
    *,
    arc_request: ARCRequest,
    owner: Optional[Owner] = None,
    requester: Optional[User] = None,
) -> Dict[str, str]:
    now = datetime.now(timezone.utc)
    context = sample_merge_context()
    context.update(
        {
            "current_date": now.date().isoformat(),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M %Z"),
        }
    )

    request_reference = f"ARC-{arc_request.id}"
    decision_value = "APPROVED" if arc_request.status == "PASSED" else "NOT APPROVED"
    submitted_at = arc_request.submitted_at
    decision_at = arc_request.final_decision_at
    requester_name = ""
    requester_email = ""
    if requester:
        requester_name = requester.full_name or requester.email or ""
        requester_email = requester.email or ""
    if owner and not requester_name:
        requester_name = owner.primary_name
        requester_email = owner.primary_email or ""

    conditions = arc_request.conditions or []
    condition_lines = []
    for condition in conditions:
        label = "Requirement" if condition.condition_type == "REQUIREMENT" else "Comment"
        condition_lines.append(f"{label}: {condition.text}")
    condition_text = "\n".join(condition_lines) if condition_lines else "None"

    attachments = arc_request.attachments or []
    attachment_text = ", ".join(
        [attachment.original_filename or attachment.stored_filename for attachment in attachments]
    )
    if not attachment_text:
        attachment_text = "None"

    portal_url = f"{settings.frontend_url}/arc?requestId={arc_request.id}"

    context.update(
        {
            "arc_request_reference": request_reference,
            "arc_request_id": str(arc_request.id),
            "arc_request_title": arc_request.title,
            "arc_request_project_type": arc_request.project_type or "",
            "arc_request_description": arc_request.description or "",
            "arc_request_submitted_at": submitted_at.strftime("%Y-%m-%d %H:%M %Z") if submitted_at else "",
            "arc_request_decision_at": decision_at.strftime("%Y-%m-%d %H:%M %Z") if decision_at else "",
            "arc_request_decision": decision_value,
            "arc_request_requester_name": requester_name,
            "arc_request_requester_email": requester_email,
            "arc_property_address": owner.property_address if owner else "",
            "arc_property_lot": owner.lot if owner else "",
            "arc_request_conditions": condition_text,
            "arc_request_attachments": attachment_text,
            "arc_request_portal_url": portal_url,
        }
    )
    return context


def render_merge_tags(text: str, context: Dict[str, str]) -> str:
    if not text:
        return text

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(context.get(key, match.group(0)))

    return TAG_PATTERN.sub(_replace, text)


def render_template(subject: str, body: str, context: Dict[str, str]) -> Dict[str, str]:
    return {
        "subject": render_merge_tags(subject, context),
        "body": render_merge_tags(body, context),
    }
