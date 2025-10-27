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
