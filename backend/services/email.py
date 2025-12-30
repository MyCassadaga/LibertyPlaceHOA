import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ..config import settings

logger = logging.getLogger(__name__)

MAX_LOG_RECIPIENTS = 3
MAX_SUBJECT_PREVIEW = 12


@dataclass
class SendResult:
    backend: str
    status_code: Optional[int]
    request_id: Optional[str]
    error: Optional[str]


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    name, domain = value.split("@", 1)
    if not name:
        masked = "***"
    elif len(name) <= 2:
        masked = f"{name[0]}***"
    else:
        masked = f"{name[0]}***{name[-1]}"
    return f"{masked}@{domain}"


def _mask_subject(subject: str) -> str:
    if not subject:
        return ""
    preview = subject[:MAX_SUBJECT_PREVIEW]
    return f"{preview}… (len={len(subject)})"


def log_email_configuration() -> None:
    backend = (settings.email_backend or "local").strip().strip("'\"").lower()
    logger.info(
        "Email configuration: backend=%s sendgrid_api_key=%s email_host=%s email_host_user=%s "
        "email_host_password=%s email_from_address=%s email_reply_to=%s",
        backend,
        bool(settings.sendgrid_api_key),
        bool(settings.email_host),
        bool(settings.email_host_user),
        bool(settings.email_host_password),
        bool(settings.email_from_address),
        bool(settings.email_reply_to),
    )


def _normalize_recipients(recipients: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for email in recipients:
        if not email:
            continue
        cleaned = email.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(cleaned)
    return normalized


def _resolve_sender() -> Tuple[str, str]:
    from_address = settings.email_from_address or "admin@libertyplacehoa.com"
    display_name = settings.email_from_name or "Liberty Place HOA"
    return from_address, display_name


def _write_local_email(subject: str, body: str, recipients: List[str]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
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


def _send_via_sendgrid(subject: str, body: str, recipients: List[str]) -> SendResult:
    from_address, display_name = _resolve_sender()
    if not settings.sendgrid_api_key or not from_address:
        raise RuntimeError("SendGrid backend requires SENDGRID_API_KEY and EMAIL_FROM_ADDRESS.")

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Email, Mail
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("SendGrid backend requires the sendgrid package.") from exc

    reply_to = settings.email_reply_to or from_address
    from_email = Email(email=from_address, name=display_name)
    reply_to_email = Email(email=reply_to) if reply_to else None
    message = Mail(
        from_email=from_email,
        to_emails=recipients,
        subject=subject,
        plain_text_content=body,
    )
    if reply_to_email:
        message.reply_to = reply_to_email
    client = SendGridAPIClient(settings.sendgrid_api_key)
    try:
        response = client.send(message)
    except Exception as exc:  # pragma: no cover - runtime guard
        status_code = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None)
        request_id = None
        headers = getattr(exc, "headers", None) or {}
        if isinstance(headers, dict):
            request_id = headers.get("X-Message-Id") or headers.get("X-Request-Id")
        logger.exception(
            "SendGrid dispatch failed (status=%s request_id=%s body=%s).",
            status_code,
            request_id,
            body,
        )
        return SendResult(backend="sendgrid", status_code=status_code, request_id=request_id, error=str(exc))

    request_id = None
    if isinstance(response.headers, dict):
        request_id = response.headers.get("X-Message-Id") or response.headers.get("X-Request-Id")
    logger.info(
        "Sent announcement via SendGrid to %d recipients (status=%s request_id=%s).",
        len(recipients),
        response.status_code,
        request_id,
    )
    return SendResult(backend="sendgrid", status_code=response.status_code, request_id=request_id, error=None)


def _send_via_smtp(subject: str, body: str, recipients: List[str]) -> SendResult:
    if not settings.email_host:
        raise RuntimeError("SMTP backend requires EMAIL_HOST.")
    if not settings.email_host_user or not settings.email_host_password:
        raise RuntimeError("SMTP backend requires EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.")
    from_address, display_name = _resolve_sender()
    if not from_address:
        raise RuntimeError("SMTP backend requires EMAIL_FROM_ADDRESS.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((display_name, from_address))
    message["To"] = ", ".join(recipients)
    reply_to = settings.email_reply_to or from_address
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    port = settings.email_port or 587
    use_tls = getattr(settings, "email_use_tls", True)
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.email_host, port) as connection:
        connection.ehlo()
        if use_tls:
            connection.starttls(context=context)
            connection.ehlo()
        connection.login(settings.email_host_user, settings.email_host_password)
        connection.send_message(message)
    logger.info("Sent announcement via SMTP to %d recipients.", len(recipients))
    return SendResult(backend="smtp", status_code=250, request_id=None, error=None)


def _log_send_attempt(
    backend: str,
    subject: str,
    from_address: str,
    recipients: List[str],
    reply_to: Optional[str],
) -> None:
    masked_recipients = [_mask_email(addr) for addr in recipients[:MAX_LOG_RECIPIENTS]]
    if len(recipients) > MAX_LOG_RECIPIENTS:
        masked_recipients.append(f"+{len(recipients) - MAX_LOG_RECIPIENTS} more")
    logger.info(
        "Dispatching email backend=%s from=%s reply_to=%s to=%s subject=%s",
        backend,
        _mask_email(from_address) if from_address else None,
        _mask_email(reply_to) if reply_to else None,
        masked_recipients,
        _mask_subject(subject),
    )


def send_announcement(subject: str, body: str, recipients: Iterable[str]) -> List[str]:
    """Dispatch announcements using the configured email backend."""
    recipient_list = _normalize_recipients(recipients)
    if not recipient_list:
        logger.info("Email dispatch skipped: no recipients (subject=%s).", _mask_subject(subject))
        return []

    backend = (settings.email_backend or "local").strip().strip("'\"").lower()
    from_address, _ = _resolve_sender()
    reply_to = settings.email_reply_to or from_address
    _log_send_attempt(backend, subject, from_address, recipient_list, reply_to)

    try:
        if backend == "local":
            _write_local_email(subject, body, recipient_list)
        elif backend == "sendgrid":
            _send_via_sendgrid(subject, body, recipient_list)
        elif backend in {"smtp", "sendgrid_smtp"}:
            _send_via_smtp(subject, body, recipient_list)
        else:
            logger.warning("Unknown EMAIL_BACKEND '%s'. Defaulting to local stub.", backend)
            _write_local_email(subject, body, recipient_list)
    except Exception:
        logger.exception("Email dispatch failed for backend=%s.", backend)
        raise

    return recipient_list


def send_announcement_with_result(subject: str, body: str, recipients: Iterable[str]) -> SendResult:
    recipient_list = _normalize_recipients(recipients)
    backend = (settings.email_backend or "local").strip().strip("'\"").lower()
    from_address, _ = _resolve_sender()
    reply_to = settings.email_reply_to or from_address
    _log_send_attempt(backend, subject, from_address, recipient_list, reply_to)

    if not recipient_list:
        logger.info("Email dispatch skipped: no recipients (subject=%s).", _mask_subject(subject))
        return SendResult(backend=backend, status_code=None, request_id=None, error="No recipients provided.")

    try:
        if backend == "local":
            _write_local_email(subject, body, recipient_list)
            return SendResult(backend="local", status_code=200, request_id=None, error=None)
        if backend == "sendgrid":
            return _send_via_sendgrid(subject, body, recipient_list)
        if backend in {"smtp", "sendgrid_smtp"}:
            return _send_via_smtp(subject, body, recipient_list)

        logger.warning("Unknown EMAIL_BACKEND '%s'. Defaulting to local stub.", backend)
        _write_local_email(subject, body, recipient_list)
        return SendResult(backend="local", status_code=200, request_id=None, error=None)
    except Exception as exc:
        logger.exception("Email dispatch failed for backend=%s.", backend)
        return SendResult(backend=backend, status_code=None, request_id=None, error=str(exc))


def send_notice_email(recipient: str, subject: str, body_html: str) -> None:
    if not recipient:
        raise ValueError("Recipient email required")
    send_announcement(subject, body_html, [recipient])
