import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..config import settings
from ..models.models import Notice, PaperworkItem, User
from ..schemas.schemas import PaperworkDispatchRequest, PaperworkListItem, UserRead
from ..services.audit import audit_log
from ..services.certified_mail import CertifiedMailError, certified_mail_client
from ..services.click2mail import Click2MailError, click2mail_client
from ..utils.pdf_utils import generate_notice_letter_pdf

router = APIRouter(prefix="/paperwork", tags=["paperwork"])

BOARD_ROLES = ("BOARD", "TREASURER", "SECRETARY", "SYSADMIN")
DELIVERY_METHOD_STANDARD = "STANDARD_MAIL"
DELIVERY_METHOD_CERTIFIED = "CERTIFIED_MAIL"


def _owner_address(owner) -> str:
    address = owner.mailing_address or owner.property_address or "Address on file"
    return address


def _serialize_paperwork(item: PaperworkItem) -> PaperworkListItem:
    claimed_by = UserRead.from_orm(item.claimed_by) if item.claimed_by else None
    return PaperworkListItem(
        id=item.id,
        notice_id=item.notice_id,
        owner_id=item.owner_id,
        owner_name=item.owner.primary_name,
        owner_address=_owner_address(item.owner),
        notice_type_code=item.notice.notice_type.code,
        subject=item.notice.subject,
        required=item.required,
        status=item.status,
        delivery_method=item.delivery_method,
        delivery_provider=item.delivery_provider,
        provider_status=item.provider_status,
        provider_job_id=item.provider_job_id,
        tracking_number=item.tracking_number,
        delivery_status=item.delivery_status,
        delivered_at=item.delivered_at,
        pdf_available=bool(item.pdf_path),
        claimed_by=claimed_by,
        claimed_at=item.claimed_at,
        mailed_at=item.mailed_at,
        created_at=item.created_at,
    )


@router.get("/features")
def paperwork_features(
    _: User = Depends(require_roles(*BOARD_ROLES)),
) -> dict:
    return {
        "click2mail_enabled": click2mail_client.is_configured,
        "certified_mail_enabled": settings.certified_mail_enabled,
    }


@router.get("/", response_model=List[PaperworkListItem])
def list_paperwork(
    status: Optional[str] = Query(None),
    requiredOnly: bool = Query(False, alias="requiredOnly"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*BOARD_ROLES)),
) -> List[PaperworkListItem]:
    query = (
        db.query(PaperworkItem)
        .options(
            joinedload(PaperworkItem.owner),
            joinedload(PaperworkItem.notice).joinedload(Notice.notice_type),
            joinedload(PaperworkItem.claimed_by),
        )
        .order_by(PaperworkItem.created_at.asc())
    )
    if status:
        query = query.filter(PaperworkItem.status == status.upper())
    else:
        query = query.filter(PaperworkItem.status.in_(["PENDING", "CLAIMED"]))
    if requiredOnly:
        query = query.filter(PaperworkItem.required.is_(True))
    items = query.all()
    return [_serialize_paperwork(item) for item in items]


@router.post("/{paperwork_id}/claim", response_model=PaperworkListItem)
def claim_paperwork(
    paperwork_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_ROLES)),
) -> PaperworkListItem:
    item = (
        db.query(PaperworkItem)
        .options(
            joinedload(PaperworkItem.owner),
            joinedload(PaperworkItem.notice).joinedload(Notice.notice_type),
            joinedload(PaperworkItem.claimed_by),
        )
        .filter(PaperworkItem.id == paperwork_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paperwork item not found")
    if item.status not in {"PENDING", "CLAIMED"}:
        raise HTTPException(status_code=400, detail="Paperwork already mailed")
    if item.status == "CLAIMED" and item.claimed_by_board_member_id not in {None, user.id}:
        raise HTTPException(status_code=409, detail="Already claimed by another board member")
    item.status = "CLAIMED"
    item.claimed_by_board_member_id = user.id
    item.claimed_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_paperwork(item)


@router.post("/{paperwork_id}/mail", response_model=PaperworkListItem)
def mark_paperwork_mailed(
    paperwork_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_ROLES)),
) -> PaperworkListItem:
    item = (
        db.query(PaperworkItem)
        .options(
            joinedload(PaperworkItem.owner),
            joinedload(PaperworkItem.notice).joinedload(Notice.notice_type),
            joinedload(PaperworkItem.claimed_by),
        )
        .filter(PaperworkItem.id == paperwork_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paperwork item not found")
    if item.status == "MAILED":
        return _serialize_paperwork(item)
    item.status = "MAILED"
    item.mailed_at = datetime.now(timezone.utc)
    if not item.delivery_method:
        item.delivery_method = "MANUAL"
    item.notice.delivery_method = item.delivery_method
    item.notice.status = "MAILED"
    item.notice.mailed_at = item.mailed_at
    db.add_all([item, item.notice])
    db.commit()
    db.refresh(item)
    return _serialize_paperwork(item)


def _load_dispatch_item(db: Session, paperwork_id: int) -> PaperworkItem:
    item = (
        db.query(PaperworkItem)
        .options(
            joinedload(PaperworkItem.owner),
            joinedload(PaperworkItem.notice).joinedload(Notice.notice_type),
        )
        .filter(PaperworkItem.id == paperwork_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paperwork item not found")
    if not item.notice:
        raise HTTPException(status_code=400, detail="Paperwork item is missing a notice reference.")
    return item


def _load_pdf_bytes(item: PaperworkItem) -> bytes:
    if item.pdf_path and Path(item.pdf_path).exists():
        pdf_path_obj = Path(item.pdf_path)
    else:
        generated_path = generate_notice_letter_pdf(item.notice, item.owner)
        pdf_path_obj = Path(generated_path)
        item.pdf_path = generated_path
    return pdf_path_obj.read_bytes()


def _parse_delivered_at(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


@router.post("/{paperwork_id}/dispatch", response_model=PaperworkListItem)
def dispatch_paperwork(
    paperwork_id: int,
    payload: PaperworkDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_ROLES)),
) -> PaperworkListItem:
    item = _load_dispatch_item(db, paperwork_id)
    if item.status == "MAILED":
        return _serialize_paperwork(item)

    try:
        pdf_bytes = _load_pdf_bytes(item)
        if payload.delivery_method == DELIVERY_METHOD_STANDARD:
            if not click2mail_client.is_configured:
                raise HTTPException(status_code=400, detail="Click2Mail integration is not configured.")
            job = click2mail_client.dispatch_notice(item.notice, item.owner, pdf_bytes)
            provider = "CLICK2MAIL"
            provider_status = job.get("status") or "QUEUED"
            provider_job_id = str(job.get("id") or job.get("jobId") or "")
            tracking_number = job.get("trackingNumber") or job.get("tracking_number")
            provider_meta = job
            delivery_status = provider_status
            delivered_at = _parse_delivered_at(job.get("deliveredAt") or job.get("delivered_at"))
        elif payload.delivery_method == DELIVERY_METHOD_CERTIFIED:
            if not certified_mail_client.is_configured:
                raise HTTPException(status_code=400, detail="Certified mail integration is not configured.")
            response = certified_mail_client.dispatch_notice(item.notice, item.owner, pdf_bytes)
            provider = "CERTIFIED_MAIL"
            provider_status = response.get("status") or "QUEUED"
            provider_job_id = str(response.get("id") or response.get("jobId") or "")
            tracking_number = response.get("trackingNumber") or response.get("tracking_number")
            provider_meta = response
            delivery_status = response.get("deliveryStatus") or provider_status
            delivered_at = _parse_delivered_at(response.get("deliveredAt") or response.get("delivered_at"))
        else:
            raise HTTPException(status_code=400, detail="Unsupported delivery method.")
    except FileNotFoundError as exc:
        logger = logging.getLogger(__name__)
        logger.exception("Unable to read generated notice PDF for dispatch.")
        raise HTTPException(status_code=500, detail="Unable to generate notice PDF.") from exc
    except (Click2MailError, CertifiedMailError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    item.status = "MAILED"
    item.mailed_at = datetime.now(timezone.utc)
    item.delivery_method = payload.delivery_method
    item.delivery_provider = provider
    item.provider_job_id = provider_job_id
    item.provider_status = provider_status
    item.provider_meta = provider_meta
    item.tracking_number = tracking_number
    item.delivery_status = delivery_status
    item.delivered_at = delivered_at
    item.notice.status = "MAILED"
    item.notice.mailed_at = item.mailed_at
    item.notice.delivery_method = payload.delivery_method
    item.notice.tracking_number = tracking_number
    item.notice.delivery_status = delivery_status
    item.notice.delivered_at = delivered_at
    db.add_all([item, item.notice])
    db.commit()
    db.refresh(item)
    if payload.delivery_method == DELIVERY_METHOD_CERTIFIED:
        audit_log(
            db_session=db,
            actor_user_id=user.id,
            action="paperwork.certified_dispatch",
            target_entity_type="PaperworkItem",
            target_entity_id=str(item.id),
            after={
                "delivery_method": payload.delivery_method,
                "provider": provider,
                "tracking_number": tracking_number,
            },
        )
    return _serialize_paperwork(item)


@router.post("/{paperwork_id}/dispatch-click2mail", response_model=PaperworkListItem)
def dispatch_click2mail(
    paperwork_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*BOARD_ROLES)),
) -> PaperworkListItem:
    payload = PaperworkDispatchRequest(delivery_method=DELIVERY_METHOD_STANDARD)
    return dispatch_paperwork(paperwork_id, payload, db, user)


@router.get("/{paperwork_id}/print", response_class=HTMLResponse)
def print_paperwork(
    paperwork_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*BOARD_ROLES)),
):
    item = (
        db.query(PaperworkItem)
        .options(
            joinedload(PaperworkItem.owner),
            joinedload(PaperworkItem.notice).joinedload(Notice.notice_type),
        )
        .filter(PaperworkItem.id == paperwork_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paperwork item not found")
    owner = item.owner
    notice = item.notice
    address = _owner_address(owner)
    html = f"""
    <html>
      <body>
        <div style='font-family: sans-serif; max-width: 700px; margin: 0 auto;'>
          <h2>Liberty Place HOA</h2>
          <p>{address}</p>
          <hr />
          <h3>{notice.subject}</h3>
          <div>{notice.body_html}</div>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/{paperwork_id}/download")
def download_paperwork_pdf(
    paperwork_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*BOARD_ROLES)),
):
    item = db.query(PaperworkItem).filter(PaperworkItem.id == paperwork_id).first()
    if not item or not item.pdf_path:
        raise HTTPException(status_code=404, detail="Paperwork PDF not found")
    pdf_path = Path(item.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Paperwork PDF is missing on disk")
    filename = pdf_path.name if pdf_path.suffix else f"paperwork-{paperwork_id}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)
