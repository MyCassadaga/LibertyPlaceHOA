from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy.orm import Session

from ..models.models import Invoice, LedgerEntry, Owner


@dataclass
class CsvReport:
    filename: str
    content: str


def _render_csv(headers: List[str], rows: Iterable[Iterable[str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def generate_ar_aging_report(session: Session, as_of: date | None = None) -> CsvReport:
    today = as_of or date.today()
    invoices = (
        session.query(Invoice)
        .filter(Invoice.status == "OPEN")
        .order_by(Invoice.due_date.asc())
        .all()
    )

    rows: List[List[str]] = []
    headers = [
        "Owner",
        "Lot",
        "Invoice ID",
        "Original Amount",
        "Amount Due",
        "Due Date",
        "Days Past Due",
        "Aging Bucket",
    ]

    for invoice in invoices:
        days_past_due = (today - invoice.due_date).days
        if days_past_due < 0:
            bucket = "Current"
        elif days_past_due <= 30:
            bucket = "1-30"
        elif days_past_due <= 60:
            bucket = "31-60"
        elif days_past_due <= 90:
            bucket = "61-90"
        else:
            bucket = "90+"

        owner = session.get(Owner, invoice.owner_id)
        amount_due = Decimal(invoice.amount or 0)
        rows.append(
            [
                owner.primary_name if owner else "Unknown",
                owner.lot if owner else "",
                str(invoice.id),
                f"{Decimal(invoice.original_amount or 0):.2f}",
                f"{amount_due:.2f}",
                invoice.due_date.isoformat(),
                str(max(0, days_past_due)),
                bucket,
            ]
        )

    csv_content = _render_csv(headers, rows)
    filename = f"ar-aging-{today.isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)


def generate_cash_flow_report(session: Session, months: int = 12) -> CsvReport:
    entries = (
        session.query(LedgerEntry)
        .order_by(LedgerEntry.timestamp.asc())
        .all()
    )

    monthly_totals: dict[str, Decimal] = {}
    for entry in entries:
        month_key = (entry.timestamp or datetime.utcnow()).strftime("%Y-%m")
        monthly_totals.setdefault(month_key, Decimal("0.00"))
        monthly_totals[month_key] += Decimal(entry.amount or 0)

    sorted_months = sorted(monthly_totals.keys())[-months:]
    headers = ["Month", "Net Cash Flow"]
    rows = [[month, f"{monthly_totals[month]:.2f}"] for month in sorted_months]

    csv_content = _render_csv(headers, rows)
    filename = f"cash-flow-{datetime.utcnow().date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)
