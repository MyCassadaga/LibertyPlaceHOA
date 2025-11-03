from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import ARCRequest, Invoice, LedgerEntry, Owner, Violation


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
        .join(Owner, Owner.id == Invoice.owner_id)
        .filter(Invoice.status == "OPEN")
        .filter(Owner.is_archived.is_(False))
        .order_by(Invoice.due_date.asc())
        .all()
    )

    headers = [
        "Owner",
        "Property Address",
        "Invoice ID",
        "Original Amount",
        "Amount Due",
        "Due Date",
        "Days Past Due",
        "Aging Bucket",
    ]
    rows: List[List[str]] = []

    for invoice in invoices:
        owner = session.get(Owner, invoice.owner_id)
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

        rows.append(
            [
                owner.primary_name if owner else "Unknown",
                owner.property_address if owner else "",
                str(invoice.id),
                f"{Decimal(invoice.original_amount or 0):.2f}",
                f"{Decimal(invoice.amount or 0):.2f}",
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
        .join(Owner, Owner.id == LedgerEntry.owner_id)
        .filter(Owner.is_archived.is_(False))
        .order_by(LedgerEntry.timestamp.asc())
        .all()
    )

    monthly_totals: dict[str, Decimal] = {}
    for entry in entries:
        timestamp = entry.timestamp or datetime.utcnow()
        month_key = timestamp.strftime("%Y-%m")
        monthly_totals.setdefault(month_key, Decimal("0.00"))
        monthly_totals[month_key] += Decimal(entry.amount or 0)

    sorted_months = sorted(monthly_totals.keys())[-months:]
    headers = ["Month", "Net Cash Flow"]
    rows = [[month, f"{monthly_totals[month]:.2f}"] for month in sorted_months]

    csv_content = _render_csv(headers, rows)
    filename = f"cash-flow-{datetime.utcnow().date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)


def generate_violations_summary_report(session: Session) -> CsvReport:
    total = session.query(func.count(Violation.id)).scalar() or 0
    open_statuses = {"NEW", "UNDER_REVIEW", "WARNING_SENT", "HEARING", "FINE_ACTIVE"}
    open_count = (
        session.query(func.count(Violation.id))
        .filter(Violation.status.in_(open_statuses))
        .scalar()
        or 0
    )

    status_counts = (
        session.query(Violation.status, func.count(Violation.id))
        .group_by(Violation.status)
        .all()
    )
    category_counts = (
        session.query(Violation.category, func.count(Violation.id))
        .group_by(Violation.category)
        .all()
    )

    headers = ["Metric", "Value"]
    rows: List[List[str]] = [
        ["Total Violations", str(total)],
        ["Open Violations", str(open_count)],
    ]

    for status, count in status_counts:
        rows.append([f"Status: {status}", str(count)])

    for category, count in category_counts:
        rows.append([f"Category: {category}", str(count)])

    csv_content = _render_csv(headers, rows)
    filename = f"violations-summary-{datetime.utcnow().date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)


def generate_arc_sla_report(session: Session) -> CsvReport:
    requests = session.query(ARCRequest).all()
    decision_durations: List[int] = []
    completion_durations: List[int] = []
    revision_count = 0

    for arc_request in requests:
        if arc_request.submitted_at and arc_request.final_decision_at:
            decision_durations.append(
                (arc_request.final_decision_at - arc_request.submitted_at).days
            )
        if arc_request.submitted_at and arc_request.completed_at:
            completion_durations.append(
                (arc_request.completed_at - arc_request.submitted_at).days
            )
        if arc_request.revision_requested_at:
            revision_count += 1

    def _average(values: List[int]) -> str:
        if not values:
            return "N/A"
        return f"{sum(values) / len(values):.1f}"

    headers = ["Metric", "Value"]
    rows = [
        ["Total Requests", str(len(requests))],
        ["Avg Days to Decision", _average(decision_durations)],
        ["Avg Days to Completion", _average(completion_durations)],
        ["Requests with Revision", str(revision_count)],
    ]

    csv_content = _render_csv(headers, rows)
    filename = f"arc-sla-{datetime.utcnow().date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)
