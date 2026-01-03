from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import case
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import Contract, User
from ..schemas.schemas import ContractCreate, ContractRead, ContractUpdate
from ..services.audit import audit_log
from ..services.storage import storage_service

router = APIRouter()

EDITOR_ROLES = ("TREASURER", "SYSADMIN")


def _get_contract_or_404(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


def _serialize_contract(contract: Contract) -> ContractRead:
    download_url = f"/contracts/{contract.id}/attachment" if contract.file_path else None
    return ContractRead(
        id=contract.id,
        vendor_name=contract.vendor_name,
        service_type=contract.service_type,
        start_date=contract.start_date,
        end_date=contract.end_date,
        auto_renew=contract.auto_renew,
        termination_notice_deadline=contract.termination_notice_deadline,
        file_path=contract.file_path,
        attachment_file_name=contract.attachment_file_name,
        attachment_content_type=contract.attachment_content_type,
        attachment_file_size=contract.attachment_file_size,
        attachment_uploaded_at=contract.attachment_uploaded_at,
        attachment_download_url=download_url,
        value=contract.value,
        notes=contract.notes,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


@router.get("/", response_model=List[ContractRead])
def list_contracts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN", "ATTORNEY", "AUDITOR")),
) -> List[ContractRead]:
    contracts = (
        db.query(Contract)
        .order_by(
            case((Contract.end_date.is_(None), 1), else_=0),
            Contract.end_date.asc(),
        )
        .all()
    )
    return [_serialize_contract(contract) for contract in contracts]


@router.post("/", response_model=ContractRead)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*EDITOR_ROLES)),
) -> ContractRead:
    contract = Contract(**payload.dict())
    db.add(contract)
    db.commit()
    db.refresh(contract)
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="contracts.create",
        target_entity_type="Contract",
        target_entity_id=str(contract.id),
        after=payload.dict(),
    )
    return _serialize_contract(contract)


@router.patch("/{contract_id}", response_model=ContractRead)
def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*EDITOR_ROLES)),
) -> ContractRead:
    contract = _get_contract_or_404(db, contract_id)
    before = {column.name: getattr(contract, column.name) for column in Contract.__table__.columns}
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(contract, key, value)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    after = {column.name: getattr(contract, column.name) for column in Contract.__table__.columns}
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="contracts.update",
        target_entity_type="Contract",
        target_entity_id=str(contract.id),
        before=before,
        after=after,
    )
    return _serialize_contract(contract)


@router.post("/{contract_id}/attachment", response_model=ContractRead)
async def upload_contract_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*EDITOR_ROLES)),
) -> ContractRead:
    contract = _get_contract_or_404(db, contract_id)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Attachment is empty")
    filename = file.filename or "contract.pdf"
    is_pdf = filename.lower().endswith(".pdf")
    if file.content_type and file.content_type != "application/pdf" and not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF attachments are supported")
    timestamp = datetime.now(timezone.utc).timestamp()
    relative_path = f"contracts/{contract_id}/attachment_{timestamp}_{filename}"
    stored = storage_service.save_file(relative_path, content, content_type=file.content_type)
    if contract.file_path:
        storage_service.delete_file(contract.file_path)
    contract.file_path = stored.relative_path
    contract.attachment_file_name = filename
    contract.attachment_content_type = file.content_type
    contract.attachment_file_size = len(content)
    contract.attachment_uploaded_at = datetime.now(timezone.utc)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.get("/{contract_id}/attachment")
def download_contract_attachment(
    contract_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    contract = _get_contract_or_404(db, contract_id)
    if not contract.file_path:
        raise HTTPException(status_code=404, detail="Attachment not found")
    stored = storage_service.retrieve_file(contract.file_path)
    filename = contract.attachment_file_name or f"contract-{contract_id}.pdf"
    return Response(
        content=stored.content,
        media_type=stored.content_type or contract.attachment_content_type or "application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
