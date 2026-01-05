from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Template, User
from ..schemas.schemas import TemplateCreate, TemplateMergeTag, TemplateRead, TemplateUpdate
from ..services.audit import audit_log
from ..services.templates import merge_tag_definitions

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/merge-tags", response_model=List[TemplateMergeTag])
def list_merge_tags(
    _: User = Depends(require_roles("SYSADMIN")),
) -> List[TemplateMergeTag]:
    return [TemplateMergeTag(**tag) for tag in merge_tag_definitions()]


@router.get("/", response_model=List[TemplateRead])
def list_templates(
    template_type: Optional[str] = None,
    include_archived: bool = False,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("SYSADMIN")),
) -> List[Template]:
    templates_query = db.query(Template)
    if template_type:
        templates_query = templates_query.filter(Template.type == template_type)
    if not include_archived:
        templates_query = templates_query.filter(Template.is_archived.is_(False))
    if query:
        like_query = f"%{query.strip()}%"
        templates_query = templates_query.filter(
            or_(Template.name.ilike(like_query), Template.subject.ilike(like_query))
        )
    return templates_query.order_by(Template.updated_at.desc()).all()


@router.post("/", response_model=TemplateRead)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Template:
    template = Template(
        name=payload.name.strip(),
        type=payload.type.strip(),
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        is_archived=payload.is_archived,
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="templates.create",
        target_entity_type="Template",
        target_entity_id=str(template.id),
        after={
            "name": template.name,
            "type": template.type,
            "is_archived": template.is_archived,
        },
    )
    return template


def _get_template_or_404(db: Session, template_id: int) -> Template:
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("SYSADMIN")),
) -> Template:
    return _get_template_or_404(db, template_id)


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSADMIN")),
) -> Template:
    template = _get_template_or_404(db, template_id)
    before = {column.name: getattr(template, column.name) for column in Template.__table__.columns}
    update_data = payload.dict(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()
    if "type" in update_data and update_data["type"] is not None:
        update_data["type"] = update_data["type"].strip()
    if "subject" in update_data and update_data["subject"] is not None:
        update_data["subject"] = update_data["subject"].strip()
    if "body" in update_data and update_data["body"] is not None:
        update_data["body"] = update_data["body"].strip()

    for key, value in update_data.items():
        setattr(template, key, value)
    template.updated_by_user_id = actor.id
    db.add(template)
    db.commit()
    db.refresh(template)
    after = {column.name: getattr(template, column.name) for column in Template.__table__.columns}

    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="templates.update",
        target_entity_type="Template",
        target_entity_id=str(template.id),
        before=before,
        after=after,
    )
    return template
