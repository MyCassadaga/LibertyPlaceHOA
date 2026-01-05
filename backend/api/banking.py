from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import BankTransaction, Reconciliation, User, BankBalanceSnapshot
from ..schemas.schemas import (
    BankBalanceSnapshotCreate,
    BankBalanceSnapshotRead,
    BankImportSummary,
    BankTransactionRead,
    ReconciliationRead,
)
from ..services import bank_reconciliation
from ..services.audit import audit_log

router = APIRouter(prefix="/banking", tags=["banking"])


def _as_reconciliation_read(obj: Reconciliation) -> ReconciliationRead:
    return ReconciliationRead.from_orm(obj)


@router.post("/reconciliations/import", response_model=BankImportSummary)
async def import_reconciliation(
    statement_date: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> BankImportSummary:
    parsed_date = None
    if statement_date:
        try:
            parsed_date = datetime.strptime(statement_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="statement_date must be YYYY-MM-DD") from exc

    reconciliation = bank_reconciliation.import_bank_statement(db, actor, parsed_date, note, file)
    db.commit()
    db.refresh(reconciliation)
    reconciliation = (
        db.query(Reconciliation)
        .options(joinedload(Reconciliation.transactions))
        .get(reconciliation.id)
    )
    if not reconciliation:
        raise HTTPException(status_code=404, detail="Reconciliation not found after import")
    return BankImportSummary(reconciliation=_as_reconciliation_read(reconciliation))


@router.get("/reconciliations", response_model=List[ReconciliationRead])
def list_reconciliations(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> List[Reconciliation]:
    reconciliations = (
        db.query(Reconciliation)
        .options(joinedload(Reconciliation.transactions))
        .order_by(Reconciliation.created_at.desc())
        .all()
    )
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="banking.reconciliation.list",
        target_entity_type="Reconciliation",
        target_entity_id="list",
    )
    return reconciliations


@router.get("/reconciliations/{reconciliation_id}", response_model=ReconciliationRead)
def get_reconciliation(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> Reconciliation:
    reconciliation = (
        db.query(Reconciliation)
        .options(joinedload(Reconciliation.transactions))
        .get(reconciliation_id)
    )
    if not reconciliation:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="banking.reconciliation.view",
        target_entity_type="Reconciliation",
        target_entity_id=str(reconciliation.id),
    )
    return reconciliation


@router.get("/transactions", response_model=List[BankTransactionRead])
def list_transactions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> List[BankTransaction]:
    query = db.query(BankTransaction).order_by(BankTransaction.transaction_date.desc())
    if status:
        query = query.filter(BankTransaction.status == status.upper())
    transactions = query.limit(500).all()
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="banking.transactions.list",
        target_entity_type="BankTransaction",
        target_entity_id=status or "all",
    )
    return transactions


@router.get("/balances", response_model=List[BankBalanceSnapshotRead])
def list_balance_snapshots(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("BOARD", "TREASURER", "SYSADMIN")),
) -> List[BankBalanceSnapshot]:
    return (
        db.query(BankBalanceSnapshot)
        .order_by(BankBalanceSnapshot.recorded_date.desc(), BankBalanceSnapshot.created_at.desc())
        .all()
    )


@router.post("/balances", response_model=BankBalanceSnapshotRead, status_code=201)
def create_balance_snapshot(
    payload: BankBalanceSnapshotCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("TREASURER", "SYSADMIN")),
) -> BankBalanceSnapshot:
    snapshot = BankBalanceSnapshot(
        recorded_date=payload.recorded_date,
        balance=payload.balance,
        snapshot_type=payload.snapshot_type,
        note=payload.note,
        created_by_user_id=actor.id,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    audit_log(
        db_session=db,
        actor_user_id=actor.id,
        action="banking.balance.create",
        target_entity_type="BankBalanceSnapshot",
        target_entity_id=str(snapshot.id),
        after={
            "recorded_date": snapshot.recorded_date.isoformat(),
            "balance": str(snapshot.balance),
            "snapshot_type": snapshot.snapshot_type,
        },
    )
    return snapshot
