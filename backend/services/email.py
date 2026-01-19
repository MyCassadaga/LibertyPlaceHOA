import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ..config import resolve_email_backend, settings

logger = logging.getLogger(__name__)

MAX_LOG_RECIPIENTS = 3
MAX_SUBJECT_PREVIEW = 12
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class EmailSendError:
    backend: str
    error_class: str
    message: str
    occurred_at: datetime

    def summary(self) -> str:
        timestamp = self.occurred_at.isoformat()
        detail = f"{self.error_class}: {self.message}" if self.message else self.error_class
        return f"{timestamp} backend={self.backend} {detail}"


@dataclass
class SendResult:
    backend: str
    status_code: Optional[int]
    request_id: Optional[str]
    error: Optional[str]


_last_send_error: Optional[EmailSendError] = None


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


def _mask_username(username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    if "@" in username:
        return _mask_email(username)
    if len(username) <= 2:
        return f"{username[0]}***"
    return f"{username[0]}***{username[-1]}"


def _extract_domain(address: Optional[str]) -> Optional[str]:
    if not address or "@" not in address:
        return None
    return address.split("@", 1)[1]


def _looks_like_html(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if "<html" in lowered or "<body" in lowered:
        return True
    return bool(HTML_TAG_RE.search(value))


def _resolve_body_parts(
    body: str,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    plain_text = text_body if text_body is not None else body
    html_content = html_body
    if html_content is None and _looks_like_html(body):
        html_content = body
    return plain_text, html_content


def build_email_message(
    *,
    subject: str,
    text_body: str,
    html_body: Optional[str],
    recipients: List[str],
    from_address: str,
    display_name: str,
    reply_to: Optional[str],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((display_name, from_address))
    message["To"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message

def _smtp_required_fields() -> dict[str, bool]:
    return {
        "SMTP_HOST": bool(settings.email_host),
        "SMTP_USERNAME": bool(settings.email_host_user),
        "SMTP_PASSWORD": bool(settings.email_host_password),
        "EMAIL_FROM_ADDRESS": bool(settings.email_from_address),
    }


def _select_backend() -> Tuple[str, str]:
    backend = resolve_email_backend(settings.email_backend, settings.app_env)
    reason = f"EMAIL_BACKEND={backend}"
    if backend in {"local", "file", "console"}:
        return backend, f"{reason} (local stub backend)"
    return backend, reason


def _record_send_error(backend: str, exc: Exception) -> None:
    global _last_send_error
    _last_send_error = EmailSendError(
        backend=backend,
        error_class=exc.__class__.__name__,
        message=str(exc),
        occurred_at=datetime.now(timezone.utc),
    )


def clear_last_send_error() -> None:
    global _last_send_error
    _last_send_error = None


def get_email_health_snapshot() -> dict[str, object]:
    backend, reason = _select_backend()
    smtp_required = _smtp_required_fields()
    smtp_ready = backend == "smtp" and all(smtp_required.values())
    last_error = _last_send_error.summary() if _last_send_error else None
    return {
        "backend": backend,
        "backend_reason": reason,
        "smtp_required": smtp_required,
        "smtp_ready": smtp_ready,
        "smtp_config_preview": {
            "host": settings.email_host,
            "port": settings.email_port,
            "from_address": _mask_email(settings.email_from_address) if settings.email_from_address else None,
            "username": _mask_username(settings.email_host_user),
        },
        "last_error": last_error,
    }


def log_email_configuration() -> None:
    backend, reason = _select_backend()
    smtp_required = _smtp_required_fields()
    from_domain = _extract_domain(settings.email_from_address)
    logger.info(
        "Email configuration: backend=%s email_host=%s email_port=%s email_host_user=%s email_use_tls=%s "
        "email_use_ssl=%s email_from_address=%s email_reply_to=%s",
        backend,
        settings.email_host,
        settings.email_port,
        _mask_username(settings.email_host_user),
        bool(settings.email_use_tls),
        bool(getattr(settings, "email_use_ssl", False)),
        _mask_email(settings.email_from_address) if settings.email_from_address else None,
        _mask_email(settings.email_reply_to) if settings.email_reply_to else None,
    )
    logger.info(
        "Email provider selection: backend=%s reason=%s smtp_required=%s from_domain=%s",
        backend,
        reason,
        smtp_required,
        from_domain,
    )
    if backend == "smtp":
        missing = [key for key, present in smtp_required.items() if not present]
        if missing:
            logger.error("SMTP configuration incomplete; missing=%s", missing)


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


def _smtp_error_hint(error_message: str) -> Optional[str]:
    lowered = error_message.lower()
    if "535 5.7.8" in lowered or "username and password not accepted" in lowered:
        return "Hint: credentials rejected; verify SMTP_USERNAME/SMTP_PASSWORD or use an app password."
    if "534 5.7.9" in lowered or "application-specific password required" in lowered:
        return "Hint: SMTP provider requires an application-specific password."
    if "530 5.7.0" in lowered or "must issue a starttls command first" in lowered:
        return "Hint: enable SMTP STARTTLS (EMAIL_USE_TLS=true)."
    if "550 5.7.1" in lowered or "from address not allowed" in lowered:
        return "Hint: verify EMAIL_FROM_ADDRESS matches the authenticated account or provider policy."
    return None


def _send_via_sendgrid(
    subject: str,
    body: str,
    recipients: List[str],
    from_address_override: Optional[str] = None,
    reply_to_override: Optional[str] = None,
) -> SendResult:
    from_address, display_name = _resolve_sender()
    if from_address_override:
        from_address = from_address_override
    if not settings.sendgrid_api_key or not from_address:
        raise RuntimeError("SendGrid backend requires SENDGRID_API_KEY and EMAIL_FROM_ADDRESS.")

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Email, Mail, MailSettings, SandBoxMode
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("SendGrid backend requires the sendgrid package.") from exc

    reply_to = reply_to_override or settings.email_reply_to or from_address
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
    if settings.sendgrid_sandbox_mode:
        message.mail_settings = MailSettings(sandbox_mode=SandBoxMode(enable=True))
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


def _send_via_smtp(
    subject: str,
    body: str,
    recipients: List[str],
    from_address_override: Optional[str] = None,
    reply_to_override: Optional[str] = None,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
) -> SendResult:
    if not settings.email_host:
        raise RuntimeError("SMTP backend requires SMTP_HOST (or EMAIL_HOST).")
    if not settings.email_host_user or not settings.email_host_password:
        raise RuntimeError("SMTP backend requires SMTP_USERNAME and SMTP_PASSWORD.")
    from_address, display_name = _resolve_sender()
    if from_address_override:
        from_address = from_address_override
    if not from_address:
        raise RuntimeError("SMTP backend requires EMAIL_FROM_ADDRESS.")

    reply_to = reply_to_override or settings.email_reply_to or from_address
    plain_text, html_content = _resolve_body_parts(body, text_body=text_body, html_body=html_body)
    message = build_email_message(
        subject=subject,
        text_body=plain_text,
        html_body=html_content,
        recipients=recipients,
        from_address=from_address,
        display_name=display_name,
        reply_to=reply_to,
    )

    port = settings.email_port or 587
    use_tls = getattr(settings, "email_use_tls", True)
    use_ssl = getattr(settings, "email_use_ssl", False)
    context = ssl.create_default_context()
    timeout = 20
    logger.info(
        "SMTP dispatch attempt host=%s port=%s use_tls=%s use_ssl=%s username=%s from_domain=%s recipient_domains=%s",
        settings.email_host,
        port,
        bool(use_tls),
        bool(use_ssl),
        _mask_username(settings.email_host_user),
        _extract_domain(from_address),
        list({_extract_domain(addr) for addr in recipients if _extract_domain(addr)}),
    )
    try:
        if use_ssl:
            connection = smtplib.SMTP_SSL(settings.email_host, port, timeout=timeout, context=context)
        else:
            connection = smtplib.SMTP(settings.email_host, port, timeout=timeout)
        with connection:
            connection.ehlo()
            if use_tls and not use_ssl:
                connection.starttls(context=context)
                connection.ehlo()
            connection.login(settings.email_host_user, settings.email_host_password)
            connection.send_message(message)
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPException) as exc:
        hint = _smtp_error_hint(str(exc))
        if hint:
            logger.warning("SMTP authentication error hint: %s", hint)
        raise
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


def send_announcement(
    subject: str,
    body: str,
    recipients: Iterable[str],
    *,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
) -> List[str]:
    """Dispatch announcements using the configured email backend."""
    recipient_list = _normalize_recipients(recipients)
    if not recipient_list:
        logger.info("Email dispatch skipped: no recipients (subject=%s).", _mask_subject(subject))
        return []

    backend, reason = _select_backend()
    from_address, _ = _resolve_sender()
    reply_to = settings.email_reply_to or from_address
    _log_send_attempt(backend, subject, from_address, recipient_list, reply_to)
    logger.info("Email backend resolved: backend=%s reason=%s", backend, reason)

    plain_text, html_content = _resolve_body_parts(body, text_body=text_body, html_body=html_body)
    try:
        if backend in {"local", "file", "console"}:
            _write_local_email(subject, plain_text, recipient_list)
        elif backend == "smtp":
            _send_via_smtp(
                subject,
                body,
                recipient_list,
                text_body=plain_text,
                html_body=html_content,
            )
        else:
            raise RuntimeError(f"Unsupported EMAIL_BACKEND '{backend}'.")
    except Exception as exc:
        logger.exception(
            "Email dispatch failed for backend=%s error_class=%s message=%s.",
            backend,
            exc.__class__.__name__,
            exc,
        )
        _record_send_error(backend, exc)
        raise

    return recipient_list


def send_custom_email(
    subject: str,
    body: str,
    recipients: Iterable[str],
    from_address: Optional[str] = None,
    reply_to: Optional[str] = None,
    *,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
) -> List[str]:
    recipient_list = _normalize_recipients(recipients)
    if not recipient_list:
        logger.info("Email dispatch skipped: no recipients (subject=%s).", _mask_subject(subject))
        return []

    backend, reason = _select_backend()
    fallback_from, _ = _resolve_sender()
    effective_from = from_address or fallback_from
    reply_to_address = reply_to or settings.email_reply_to or effective_from
    if not effective_from:
        raise RuntimeError("Email backend requires a sender address.")
    _log_send_attempt(backend, subject, effective_from, recipient_list, reply_to_address)
    logger.info("Email backend resolved: backend=%s reason=%s", backend, reason)

    plain_text, html_content = _resolve_body_parts(body, text_body=text_body, html_body=html_body)
    try:
        if backend in {"local", "file", "console"}:
            _write_local_email(subject, plain_text, recipient_list)
        elif backend == "smtp":
            _send_via_smtp(
                subject,
                body,
                recipient_list,
                effective_from,
                reply_to_address,
                text_body=plain_text,
                html_body=html_content,
            )
        else:
            raise RuntimeError(f"Unsupported EMAIL_BACKEND '{backend}'.")
    except Exception as exc:
        logger.exception(
            "Email dispatch failed for backend=%s error_class=%s message=%s.",
            backend,
            exc.__class__.__name__,
            exc,
        )
        _record_send_error(backend, exc)
        raise

    return recipient_list


def send_announcement_with_result(
    subject: str,
    body: str,
    recipients: Iterable[str],
    *,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
) -> SendResult:
    recipient_list = _normalize_recipients(recipients)
    backend, reason = _select_backend()
    from_address, _ = _resolve_sender()
    reply_to = settings.email_reply_to or from_address
    _log_send_attempt(backend, subject, from_address, recipient_list, reply_to)
    logger.info("Email backend resolved: backend=%s reason=%s", backend, reason)
    plain_text, html_content = _resolve_body_parts(body, text_body=text_body, html_body=html_body)

    if not recipient_list:
        logger.info("Email dispatch skipped: no recipients (subject=%s).", _mask_subject(subject))
        return SendResult(backend=backend, status_code=None, request_id=None, error="No recipients provided.")

    try:
        if backend in {"local", "file", "console"}:
            _write_local_email(subject, plain_text, recipient_list)
            return SendResult(backend="local", status_code=200, request_id=None, error=None)
        if backend == "smtp":
            return _send_via_smtp(
                subject,
                body,
                recipient_list,
                text_body=plain_text,
                html_body=html_content,
            )

        raise RuntimeError(f"Unsupported EMAIL_BACKEND '{backend}'.")
    except Exception as exc:
        logger.exception(
            "Email dispatch failed for backend=%s error_class=%s message=%s.",
            backend,
            exc.__class__.__name__,
            exc,
        )
        _record_send_error(backend, exc)
        return SendResult(
            backend=backend,
            status_code=None,
            request_id=None,
            error=f"{exc.__class__.__name__}: {exc}",
        )


def send_notice_email(recipient: str, subject: str, body_html: str) -> None:
    if not recipient:
        raise ValueError("Recipient email required")
    send_announcement(subject, body_html, [recipient], html_body=body_html)
