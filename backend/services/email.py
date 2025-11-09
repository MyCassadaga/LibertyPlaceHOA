import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from ..config import settings

logger = logging.getLogger(__name__)


def _write_local_email(subject: str, body: str, recipients: List[str]) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_subject = "".join(ch for ch in subject if ch.isalnum() or ch in (" ", "_", "-")).strip() or "email"
    filename = f"{timestamp}_{safe_subject.replace(' ', '_')}.txt"
    output_dir = Path(settings.email_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    contents = "\n".join(
        [
            f"Subject: {subject}",
            f"Recipients: {', '.join(recipients)}",
            "",
            body,
        ]
    )
    path.write_text(contents)
    logger.info("[LOCAL EMAIL] %s", path)
    return str(path)


def _send_via_sendgrid(subject: str, body: str, recipients: List[str]) -> None:
    if not settings.sendgrid_api_key or not settings.email_from_address:
        raise RuntimeError("SendGrid backend requires SENDGRID_API_KEY and EMAIL_FROM_ADDRESS.")

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("SendGrid backend requires the sendgrid package.") from exc

    message = Mail(
        from_email=(settings.email_from_address, settings.email_from_name),
        to_emails=recipients,
        subject=subject,
        plain_text_content=body,
    )
    client = SendGridAPIClient(settings.sendgrid_api_key)
    response = client.send(message)
    logger.info(
        "Sent announcement via SendGrid to %d recipients (status=%s).",
        len(recipients),
        response.status_code,
    )


def send_announcement(subject: str, body: str, recipients: Iterable[str]) -> List[str]:
    """Dispatch announcements using the configured email backend."""
    recipient_list = [email for email in recipients if email]
    if not recipient_list:
        return []

    backend = (settings.email_backend or "local").lower()

    if backend == "local":
        _write_local_email(subject, body, recipient_list)
    elif backend == "sendgrid":
        _send_via_sendgrid(subject, body, recipient_list)
    else:
        logger.warning("Unknown EMAIL_BACKEND '%s'. Defaulting to local stub.", backend)
        _write_local_email(subject, body, recipient_list)

    return recipient_list


def send_notice_email(recipient: str, subject: str, body_html: str) -> None:
    if not recipient:
        raise ValueError("Recipient email required")
    send_announcement(subject, body_html, [recipient])
