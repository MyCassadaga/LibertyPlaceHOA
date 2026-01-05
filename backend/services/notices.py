from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy.orm import Session

from ..models.models import Notice, NoticeType, Owner, PaperworkItem, User
from ..services.audit import audit_log
from ..services import email as email_service
from ..services.templates import build_merge_context, render_template
from ..utils.pdf_utils import generate_notice_letter_pdf

DeliveryChannel = Literal['EMAIL', 'PAPER', 'EMAIL_AND_PAPER']
WELCOME_NOTICE_CODE = "USPS_WELCOME"


def resolve_delivery(owner: Owner, notice_type: NoticeType) -> DeliveryChannel:
    if notice_type.requires_paper:
        if notice_type.default_delivery == 'EMAIL_AND_PAPER':
            return 'EMAIL_AND_PAPER'
        return 'PAPER'

    if owner.delivery_preference_global == 'PAPER_ALL':
        return 'PAPER'

    if not owner.primary_email:
        return 'PAPER'

    if notice_type.allow_electronic:
        if notice_type.default_delivery == 'EMAIL_ONLY':
            return 'EMAIL'
        if notice_type.default_delivery == 'PAPER_ONLY':
            return 'PAPER'
        if notice_type.default_delivery == 'EMAIL_AND_PAPER':
            return 'EMAIL_AND_PAPER'
        return 'EMAIL'

    return 'PAPER'


def _send_notice_email(owner: Owner, subject: str, body_html: str) -> None:
    if not owner.primary_email:
        raise ValueError('Owner email required for electronic delivery')
    email_service.send_notice_email(owner.primary_email, subject, body_html)


def create_notice(
    session: Session,
    *,
    owner: Owner,
    notice_type: NoticeType,
    subject: str,
    body_html: str,
    created_by: Optional[User],
) -> Notice:
    channel = resolve_delivery(owner, notice_type)
    context = build_merge_context(owner=owner, notice_type=notice_type, actor=created_by)
    rendered = render_template(subject, body_html, context)
    notice = Notice(
        owner_id=owner.id,
        notice_type_id=notice_type.id,
        subject=rendered["subject"],
        body_html=rendered["body"],
        delivery_channel=channel,
        created_by_user_id=created_by.id if created_by else None,
        status='PENDING',
    )
    session.add(notice)
    session.flush()

    paperwork: Optional[PaperworkItem] = None

    if channel in {'EMAIL', 'EMAIL_AND_PAPER'}:
        _send_notice_email(owner, subject, body_html)
        notice.status = 'SENT_EMAIL' if channel == 'EMAIL' else 'IN_PAPERWORK'
        notice.sent_email_at = datetime.now(timezone.utc)

    if channel in {'PAPER', 'EMAIL_AND_PAPER'}:
        paperwork = PaperworkItem(
            notice_id=notice.id,
            owner_id=owner.id,
            required=bool(
                notice_type.requires_paper
                or owner.delivery_preference_global == 'PAPER_ALL'
                or not owner.primary_email
            ),
            status='PENDING',
        )
        session.add(paperwork)
        if channel == 'PAPER' and notice.status == 'PENDING':
            notice.status = 'IN_PAPERWORK'
        elif channel == 'EMAIL_AND_PAPER':
            notice.status = 'IN_PAPERWORK'

    pdf_path = generate_notice_letter_pdf(notice, owner)
    if paperwork:
        paperwork.pdf_path = pdf_path

    audit_log(
        db_session=session,
        actor_user_id=created_by.id if created_by else None,
        action='notice.create',
        target_entity_type='Notice',
        target_entity_id=str(notice.id),
        after={
            'delivery_channel': channel,
            'notice_type': notice_type.code,
        },
    )
    return notice


def create_usps_welcome_notice(session: Session, owner: Owner, created_by: Optional[User]) -> Notice:
    notice_type = session.query(NoticeType).filter(NoticeType.code == WELCOME_NOTICE_CODE).first()
    if not notice_type:
        notice_type = NoticeType(
            code=WELCOME_NOTICE_CODE,
            name="USPS Welcome Packet",
            description="Draft USPS onboarding packet for new homeowners.",
            allow_electronic=False,
            requires_paper=True,
            default_delivery="PAPER_ONLY",
        )
        session.add(notice_type)
        session.flush()

    subject = "Welcome to Liberty Place HOA"
    body = (
        "Welcome to Liberty Place HOA. This packet includes important community information, "
        "rules, and next steps. Please review and reach out with any questions."
    )
    return create_notice(
        session,
        owner=owner,
        notice_type=notice_type,
        subject=subject,
        body_html=body,
        created_by=created_by,
    )
