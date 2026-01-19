import pytest
from pydantic import ValidationError

from backend.config import Settings
from backend.services import email as email_service


def test_prod_defaults_to_smtp_backend(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)
    settings = Settings(_env_file=None)

    assert settings.email_backend == "smtp"


def test_sendgrid_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("EMAIL_BACKEND", "sendgrid")

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "SendGrid backend is deprecated/removed" in str(excinfo.value)


def test_smtp_required_flags_and_ready(monkeypatch):
    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", "smtp-user@example.com")
    monkeypatch.setattr(email_service.settings, "email_host_password", "smtp-pass")
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")

    snapshot = email_service.get_email_health_snapshot()

    assert snapshot["smtp_required"]["SMTP_HOST"] is True
    assert snapshot["smtp_required"]["SMTP_USERNAME"] is True
    assert snapshot["smtp_required"]["SMTP_PASSWORD"] is True
    assert snapshot["smtp_required"]["EMAIL_FROM_ADDRESS"] is True
    assert snapshot["smtp_ready"] is True


def test_build_email_message_with_html_alternative():
    message = email_service.build_email_message(
        subject="Hello",
        text_body="Plain text",
        html_body="<p>HTML body</p>",
        recipients=["recipient@example.com"],
        from_address="no-reply@example.com",
        display_name="Liberty Place HOA",
        reply_to=None,
    )

    assert message.is_multipart()
    payload = message.get_payload()
    assert len(payload) == 2
    assert payload[0].get_content_type() == "text/plain"
    assert payload[1].get_content_type() == "text/html"
