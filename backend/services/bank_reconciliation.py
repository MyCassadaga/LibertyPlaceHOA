from __future__ import annotations

import csv
import secrets
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models.models import BankTransaction, Payment, Reconciliation, User, Invoice
from ..services.audit import audit_log

BANK_UPLOAD_DIR = Path("uploads/bank")
BANK_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _parse_amount(raw: str) -> Decimal:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return Decimal("0")
    return Decimal(cleaned)


def _parse_date(raw: str) -> Optional[datetime.date]:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _load_csv_rows(file: UploadFile) -> List[Dict[str, str]]:
    contents = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(contents.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV file missing headers.")
    expected_columns = {col.lower() for col in reader.fieldnames}
    required = {"date", "description", "amount"}
    if not required.issubset(expected_columns):
        raise ValueError("CSV must include date, description, and amount columns.")
    rows: List[Dict[str, str]] = []
    for row in reader:
        rows.append(row)
    if not rows:
        raise ValueError("CSV file contains no data rows.")
    return rows


def _match_transactions(session: Session, transactions: List[BankTransaction]) -> None:
    payments = session.query(Payment).all()
    invoices = session.query(Invoice).all()

    payment_lookup: Dict[Decimal, List[Payment]] = {}
    for payment in payments:
        amount = Decimal(payment.amount)
        payment_lookup.setdefault(amount.copy_abs().quantize(Decimal("0.01")), []).append(payment)

    invoice_lookup: Dict[Decimal, List[Invoice]] = {}
    for invoice in invoices:
        amount = Decimal(invoice.amount)
        invoice_lookup.setdefault(amount.copy_abs().quantize(Decimal("0.01")), []).append(invoice)

    used_payments: set[int] = set()
    used_invoices: set[int] = set()

    for tx in transactions:
        key = Decimal(tx.amount).copy_abs().quantize(Decimal("0.01"))
        matched = False
        # Attempt payment match first
        for payment in payment_lookup.get(key, []):
            if payment.id in used_payments:
                continue
            if tx.transaction_date and payment.date_received:
                days_diff = abs((payment.date_received.date() - tx.transaction_date).days)
                if days_diff > 3:
                    continue
            tx.matched_payment_id = payment.id
            tx.status = "MATCHED"
            used_payments.add(payment.id)
            matched = True
            break
        if matched:
            continue
        # Attempt invoice match as a fallback
        for invoice in invoice_lookup.get(key, []):
            if invoice.id in used_invoices:
                continue
            tx.matched_invoice_id = invoice.id
            tx.status = "MATCHED"
            used_invoices.add(invoice.id)
            matched = True
            break
        if not matched:
            tx.status = "UNMATCHED"


def import_bank_statement(
    session: Session,
    actor: User,
    statement_date: Optional[datetime.date],
    note: Optional[str],
    file: UploadFile,
) -> Reconciliation:
    rows = _load_csv_rows(file)

    reconciliation = Reconciliation(
        statement_date=statement_date,
        created_by_user_id=actor.id,
        note=note,
    )
    session.add(reconciliation)
    session.flush()  # get ID for filenames

    stored_filename = f"reconciliation_{reconciliation.id}_{secrets.token_hex(8)}.csv"
    target_path = BANK_UPLOAD_DIR / stored_filename
    file.file.seek(0)
    target_path.write_bytes(file.file.read())

    transactions: List[BankTransaction] = []
    for row in rows:
        amount = _parse_amount(row.get("amount", "0"))
        transaction = BankTransaction(
            reconciliation_id=reconciliation.id,
            uploaded_by_user_id=actor.id,
            transaction_date=_parse_date(row.get("date", "")),
            description=row.get("description"),
            reference=row.get("reference") or row.get("memo"),
            amount=amount,
            status="PENDING",
            source_file=str(target_path),
        )
        session.add(transaction)
        transactions.append(transaction)
    session.flush()

    _match_transactions(session, transactions)

    matched_amount = Decimal("0")
    unmatched_amount = Decimal("0")
    matched_count = 0
    for tx in transactions:
        if tx.status == "MATCHED":
            matched_count += 1
            matched_amount += Decimal(tx.amount)
        else:
            unmatched_amount += Decimal(tx.amount)

    reconciliation.total_transactions = len(transactions)
    reconciliation.matched_transactions = matched_count
    reconciliation.unmatched_transactions = reconciliation.total_transactions - matched_count
    reconciliation.matched_amount = matched_amount
    reconciliation.unmatched_amount = unmatched_amount

    session.add(reconciliation)
    session.flush()

    audit_log(
        db_session=session,
        actor_user_id=actor.id,
        action="banking.reconciliation.import",
        target_entity_type="Reconciliation",
        target_entity_id=str(reconciliation.id),
        after={
            "statement_date": statement_date.isoformat() if statement_date else None,
            "total_transactions": reconciliation.total_transactions,
            "matched_transactions": reconciliation.matched_transactions,
            "unmatched_transactions": reconciliation.unmatched_transactions,
        },
    )

    return reconciliation
