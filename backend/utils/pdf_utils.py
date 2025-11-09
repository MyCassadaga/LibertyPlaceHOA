from datetime import date, datetime
from pathlib import Path
from textwrap import wrap
from typing import Iterable, Optional
import re

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from ..config import settings

MARGIN_X = 72  # 1 inch
MARGIN_Y = 72
MAX_CHARS_PER_LINE = 90


def _output_path(filename: str) -> Path:
    base = Path(settings.pdf_output_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def _write_pdf(filename: str, lines: Iterable[str]) -> str:
    path = _output_path(filename)
    pdf_canvas = canvas.Canvas(str(path), pagesize=LETTER)
    width, height = LETTER
    text_stream = pdf_canvas.beginText(MARGIN_X, height - MARGIN_Y)
    text_stream.setFont("Helvetica", 12)

    for line in lines:
        if line is None:
            line = ""
        normalized = str(line)
        if normalized.strip() == "":
            text_stream.textLine("")
            continue
        wrapped_lines = wrap(normalized, MAX_CHARS_PER_LINE) or [normalized]
        for chunk in wrapped_lines:
            text_stream.textLine(chunk)
        text_stream.textLine("")

    pdf_canvas.drawText(text_stream)
    pdf_canvas.showPage()
    pdf_canvas.save()
    return str(path)


def generate_invoice_pdf(invoice, owner) -> str:
    address = owner.property_address or owner.mailing_address or "Pending address"
    lines = [
        "Liberty Place HOA",
        "Official Invoice",
        "",
        f"Invoice #: {invoice.id}",
        f"Bill To: {owner.primary_name}",
        f"Property Address: {address}",
        "",
        f"Amount Due: ${invoice.amount}",
        f"Due Date: {invoice.due_date}",
        "",
        "Please remit payment via the HOA portal or mail a check to the association office.",
    ]
    return _write_pdf(f"invoice_{invoice.id}.pdf", lines)


def generate_announcement_packet(announcement_subject: str, announcement_body: str) -> str:
    lines = [
        "Liberty Place HOA",
        "Community Announcement",
        "",
        f"Subject: {announcement_subject}",
        "",
    ]
    body_lines = announcement_body.splitlines() or [announcement_body]
    lines.extend(body_lines)
    return _write_pdf("announcement_packet.pdf", lines)


def generate_reminder_notice_pdf(
    invoice,
    owner,
    actor,
    days_past_due: int,
    grace_period_days: int,
    next_notice_in_days: Optional[int],
) -> str:
    today = date.today().isoformat()
    address_line = owner.mailing_address or owner.property_address or "Address pending"
    next_notice_line = (
        f"Next reminder scheduled in {next_notice_in_days} days."
        if next_notice_in_days
        else "No further reminders scheduled in the current cadence."
    )
    lines = [
        "Liberty Place HOA",
        "Accounts Receivable Reminder",
        "",
        f"Owner: {owner.primary_name}",
        f"Mailing Address: {address_line}",
        "",
        f"Invoice #{invoice.id} is {days_past_due} days past due.",
        (
            f"The {grace_period_days}-day grace period has elapsed."
            if grace_period_days
            else "Payment is now past due."
        ),
        f"Current balance: ${invoice.amount}",
        next_notice_line,
        "",
        "Please remit payment to the HOA office or via the Resident Portal.",
        f"Prepared by {actor.full_name or actor.email} on {today}",
    ]
    filename = f"invoice_{invoice.id}_reminder.pdf"
    return _write_pdf(filename, lines)


def generate_violation_notice_pdf(template_key: str, violation, owner, subject: str, body: str) -> str:
    lines = [
        "Liberty Place HOA",
        "Covenant Compliance Notice",
        "",
        f"Template: {template_key}",
        f"Owner: {owner.primary_name}",
        f"Property: {owner.property_address or owner.mailing_address or 'Pending address'}",
        "",
        f"Violation ID: {violation.id}",
        f"Current Status: {violation.status}",
        "",
        f"Subject: {subject}",
        "",
    ]
    lines.extend(body.splitlines() or [body])
    lines.append("")
    lines.append("This notice is automatically generated for association records.")
    filename = f"violation_{violation.id}_{template_key.lower()}.pdf"
    return _write_pdf(filename, lines)


def generate_attorney_notice_pdf(owner, invoices, notes: Optional[str] = None) -> str:
    from decimal import Decimal

    total_due = sum((invoice.amount for invoice in invoices), Decimal("0"))
    today = datetime.utcnow().date().isoformat()
    lines = [
        "Liberty Place HOA",
        "Attorney Engagement Packet",
        "",
        f"Date Prepared: {today}",
        f"Owner: {owner.primary_name}",
        f"Property: {owner.property_address or owner.mailing_address or 'Pending address'}",
        f"Primary Email: {owner.primary_email or 'N/A'}",
        f"Primary Phone: {owner.primary_phone or 'N/A'}",
        "",
        f"Total Outstanding Balance: ${total_due}",
        "",
        "Delinquent Invoices:",
    ]
    for invoice in invoices:
        lines.append(
            f" - Invoice #{invoice.id}: ${invoice.amount} due {invoice.due_date.isoformat()} (status: {invoice.status})"
        )
    lines.append("")
    if notes:
        lines.append("Additional Notes:")
        lines.extend(notes.splitlines())
        lines.append("")
    lines.append("This packet was generated automatically for legal review.")
    filename = f"attorney_owner_{owner.id}_{int(datetime.utcnow().timestamp())}.pdf"
    return _write_pdf(filename, lines)


def generate_notice_letter_pdf(notice, owner) -> str:
    address = owner.mailing_address or owner.property_address or "Address on file"
    lines = [
        "Liberty Place HOA",
        "",
        f"Date: {datetime.utcnow().date().isoformat()}",
        f"To: {owner.primary_name}",
        f"Property: {address}",
        "",
        f"Subject: {notice.subject}",
        "",
    ]
    body_lines = _html_to_plain_text_lines(notice.body_html)
    lines.extend(body_lines if body_lines else ["(no additional message provided)"])
    filename = f"notice_{notice.id}.pdf"
    return _write_pdf(filename, lines)


def _html_to_plain_text_lines(body_html: str) -> list[str]:
    if not body_html:
        return []
    normalized = body_html.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    stripped = re.sub(r"<[^>]+>", "", normalized)
    return [line.strip() for line in stripped.splitlines() if line.strip()]
