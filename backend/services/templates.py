from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

from ..models.models import NoticeType, Owner, User, Violation

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
