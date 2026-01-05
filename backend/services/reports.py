from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..models.models import ARCRequest, Invoice, Owner, Reconciliation, Violation


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
        .options(joinedload(Invoice.owner))
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
        owner = invoice.owner
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
    reconciliations = (
        session.query(Reconciliation)
        .order_by(Reconciliation.statement_date.desc(), Reconciliation.created_at.desc())
        .all()
    )

    headers = [
        "Statement Date",
        "Total Transactions",
        "Matched Transactions",
        "Unmatched Transactions",
        "Matched Amount",
        "Unmatched Amount",
    ]
    rows: List[List[str]] = []

    for reconciliation in reconciliations[:months]:
        statement_date = reconciliation.statement_date.isoformat() if reconciliation.statement_date else ""
        rows.append(
            [
                statement_date,
                str(reconciliation.total_transactions),
                str(reconciliation.matched_transactions),
                str(reconciliation.unmatched_transactions),
                f"{Decimal(reconciliation.matched_amount or 0):.2f}",
                f"{Decimal(reconciliation.unmatched_amount or 0):.2f}",
            ]
        )

    csv_content = _render_csv(headers, rows)
    filename = f"cash-flow-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)


def get_ar_aging_data(session: Session, as_of: date | None = None) -> List[dict]:
    today = as_of or date.today()
    invoices = (
        session.query(Invoice)
        .options(joinedload(Invoice.owner))
        .join(Owner, Owner.id == Invoice.owner_id)
        .filter(Invoice.status == "OPEN")
        .filter(Owner.is_archived.is_(False))
        .order_by(Invoice.due_date.asc())
        .all()
    )

    rows: List[dict] = []
    for invoice in invoices:
        owner = invoice.owner
        due_date = invoice.due_date
        days_past_due = (today - due_date).days if due_date else None
        rows.append(
            {
                "invoice_id": invoice.id,
                "owner_id": invoice.owner_id,
                "owner_name": owner.primary_name if owner else None,
                "lot": owner.lot if owner else None,
                "amount": str(Decimal(invoice.amount or 0)),
                "due_date": due_date,
                "status": invoice.status,
                "days_past_due": days_past_due,
            }
        )
    return rows


def get_cash_flow_data(session: Session, limit: int = 12) -> List[dict]:
    reconciliations = (
        session.query(Reconciliation)
        .order_by(Reconciliation.statement_date.desc(), Reconciliation.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "reconciliation_id": reconciliation.id,
            "statement_date": reconciliation.statement_date,
            "matched_amount": reconciliation.matched_amount,
            "unmatched_amount": reconciliation.unmatched_amount,
            "matched_transactions": reconciliation.matched_transactions,
            "unmatched_transactions": reconciliation.unmatched_transactions,
            "total_transactions": reconciliation.total_transactions,
        }
        for reconciliation in reconciliations
    ]


def get_violations_summary_data(session: Session) -> List[dict]:
    summary = (
        session.query(Violation.status, Violation.category, func.count(Violation.id))
        .group_by(Violation.status, Violation.category)
        .all()
    )
    rows: List[dict] = []
    for status, category, count in summary:
        rows.append(
            {
                "status": status,
                "category": category or "General",
                "count": count,
            }
        )
    return rows


def get_arc_sla_data(session: Session) -> List[dict]:
    requests = session.query(ARCRequest).all()
    rows: List[dict] = []

    def difference_in_days(start: datetime | None, end: datetime | None) -> int | None:
        if not start or not end:
            return None
        delta = end - start
        return max(0, delta.days)

    for arc_request in requests:
        rows.append(
            {
                "id": arc_request.id,
                "title": arc_request.title,
                "status": arc_request.status,
                "created_at": arc_request.created_at,
                "submitted_at": arc_request.submitted_at,
                "final_decision_at": arc_request.final_decision_at,
                "completed_at": arc_request.completed_at,
                "days_to_decision": difference_in_days(
                    arc_request.submitted_at, arc_request.final_decision_at
                ),
                "days_to_completion": difference_in_days(
                    arc_request.submitted_at or arc_request.created_at, arc_request.completed_at
                ),
            }
        )
    return rows


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
    filename = f"violations-summary-{datetime.now(timezone.utc).date().isoformat()}.csv"
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
    filename = f"arc-sla-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return CsvReport(filename=filename, content=csv_content)
