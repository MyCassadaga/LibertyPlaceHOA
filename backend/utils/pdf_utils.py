from datetime import date
from pathlib import Path
from tempfile import gettempdir
from typing import Optional


def generate_text_pdf_stub(filename: str, content: str) -> str:
    """Writes the provided content to a .pdf placeholder file and returns the path."""
    output_path = Path(gettempdir()) / filename
    output_path.write_text(content)
    return str(output_path)


def generate_invoice_pdf(invoice, owner) -> str:
    # Placeholder: generate a PDF in production using reportlab/weasyprint
    summary = f"Invoice #{invoice.id} for {owner.primary_name} Lot {owner.lot}\nAmount: {invoice.amount}\nDue: {invoice.due_date}"
    return generate_text_pdf_stub(f"invoice_{invoice.id}.pdf", summary)


def generate_announcement_packet(announcement_subject: str, announcement_body: str) -> str:
    packet_content = f"Subject: {announcement_subject}\n\n{announcement_body}"
    return generate_text_pdf_stub("announcement_packet.pdf", packet_content)


def generate_reminder_notice_pdf(
    invoice,
    owner,
    actor,
    days_past_due: int,
    grace_period_days: int,
    next_notice_in_days: Optional[int],
) -> str:
    today = date.today().isoformat()
    header = "Liberty Place HOA\nAccounts Receivable Reminder"
    address_line = owner.mailing_address or owner.property_address
    status_line = (
        f"Invoice #{invoice.id} for Lot {owner.lot} is {days_past_due} days past due."
    )
    grace_line = f"A {grace_period_days}-day grace period has elapsed." if grace_period_days else "Payment is now past due."
    amount_line = f"Current balance: ${invoice.amount}"
    next_notice_line = (
        f"Next reminder scheduled in {next_notice_in_days} days."
        if next_notice_in_days
        else "No further reminders scheduled in the current cadence."
    )
    closing = f"Prepared by {actor.full_name or actor.email} on {today}"
    contents = "\n\n".join(
        [
            header,
            owner.primary_name,
            address_line or "",
            status_line,
            grace_line,
            amount_line,
            next_notice_line,
            "Please remit payment to the HOA office or via the portal.",
            closing,
        ]
    )
    filename = f"invoice_{invoice.id}_reminder.pdf"
    return generate_text_pdf_stub(filename, contents)
