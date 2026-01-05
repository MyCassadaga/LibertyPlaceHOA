from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Contract, Template, User
from ..schemas.schemas import LegalMessageCreate, LegalMessageDispatch, TemplateRead
from ..services import email
from ..services.audit import audit_log

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/templates", response_model=List[TemplateRead])
def list_legal_templates(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("LEGAL", "SYSADMIN")),
) -> List[Template]:
    return (
        db.query(Template)
        .filter(Template.type == "LEGAL", Template.is_archived.is_(False))
        .order_by(Template.updated_at.desc())
        .all()
    )


@router.post("/messages", response_model=LegalMessageDispatch)
def send_legal_message(
    payload: LegalMessageCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("LEGAL", "SYSADMIN")),
) -> LegalMessageDispatch:
    contract = db.get(Contract, payload.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    if not contract.contact_email:
        raise HTTPException(status_code=400, detail="Contract is missing a contact email.")

    subject = payload.subject.strip()
    body = payload.body.strip()
    if not subject or not body:
        raise HTTPException(status_code=400, detail="Subject and body are required.")

    recipient = contract.contact_email

    def _send() -> None:
        email.send_custom_email(
            subject=subject,
            body=body,
            recipients=[recipient],
            from_address="legal@libertyplacehoa.com",
            reply_to="legal@libertyplacehoa.com",
        )

    background.add_task(_send)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="legal.message.send",
        target_entity_type="Contract",
        target_entity_id=str(contract.id),
        after={"subject": subject, "recipient": recipient},
    )

    return LegalMessageDispatch(contract_id=contract.id, recipient=recipient, sent_to=[recipient])
