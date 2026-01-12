from __future__ import annotations

from typing import List, TypedDict

from sqlalchemy.orm import Session

from ..models.models import TemplateType


class TemplateTypeSeed(TypedDict):
    code: str
    label: str
    definition: str


TEMPLATE_TYPE_SEED: List[TemplateTypeSeed] = [
    {
        "code": "ANNOUNCEMENT",
        "label": "Announcement",
        "definition": "General announcements shared with the community.",
    },
    {
        "code": "BROADCAST",
        "label": "Broadcast",
        "definition": "Broad communications sent to a selected segment.",
    },
    {
        "code": "NOTICE",
        "label": "Notice",
        "definition": "Formal notices sent to homeowners.",
    },
    {
        "code": "VIOLATION_NOTICE",
        "label": "Violation Notice",
        "definition": "Notices related to covenant violations.",
    },
    {
        "code": "ARC_REQUEST",
        "label": "ARC Request",
        "definition": "ARC decision messages for architectural review requests.",
    },
    {
        "code": "LEGAL",
        "label": "Legal",
        "definition": "Legal communications managed by the board or counsel.",
    },
    {
        "code": "BILLING_NOTICE",
        "label": "Billing Notice",
        "definition": "Emails sent to individuals as a result of billing.",
    },
]


def ensure_template_types(session: Session) -> None:
    existing = {template_type.code: template_type for template_type in session.query(TemplateType).all()}
    updated = False
    for entry in TEMPLATE_TYPE_SEED:
        template_type = existing.get(entry["code"])
        if not template_type:
            template_type = TemplateType(**entry)
            session.add(template_type)
            updated = True
        else:
            changed = False
            for field in ("label", "definition"):
                if getattr(template_type, field) != entry[field]:
                    setattr(template_type, field, entry[field])
                    changed = True
            if changed:
                updated = True
    if updated:
        session.commit()
