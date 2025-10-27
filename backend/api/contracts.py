from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import require_roles
from ..models.models import Contract, User
from ..schemas.schemas import ContractCreate, ContractRead, ContractUpdate
from ..services.audit import audit_log

router = APIRouter()


def _get_contract_or_404(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.get("/", response_model=List[ContractRead])
def list_contracts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SECRETARY", "SYSADMIN", "ATTORNEY")),
) -> List[Contract]:
    return (
        db.query(Contract)
        .order_by(
            case((Contract.end_date.is_(None), 1), else_=0),
            Contract.end_date.asc(),
        )
        .all()
    )


@router.post("/", response_model=ContractRead)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Contract:
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
    return contract


@router.patch("/{contract_id}", response_model=ContractRead)
def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Contract:
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
    return contract
