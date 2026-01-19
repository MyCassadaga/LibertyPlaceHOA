import logging

from fastapi.testclient import TestClient

from backend.api.system import require_sysadmin
from backend.main import app
from backend.services import email as email_service


def _override_sysadmin():
    class Dummy:
        id = 1

    return Dummy()


def test_email_health_prefers_smtp_when_sendgrid_configured(monkeypatch):
    monkeypatch.setattr(email_service.settings, "email_backend", "sendgrid")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", "smtp-user")
    monkeypatch.setattr(email_service.settings, "email_host_password", "smtp-pass")
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")

    client = TestClient(app)
    app.dependency_overrides[require_sysadmin] = _override_sysadmin
    try:
        response = client.get("/system/admin/email-health")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "smtp"
        assert data["smtp_required"]["SMTP_USERNAME"] is True
    finally:
        app.dependency_overrides.pop(require_sysadmin, None)
        client.close()


def test_send_announcement_with_missing_smtp_config_returns_error(monkeypatch):
    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", None)
    monkeypatch.setattr(email_service.settings, "email_host_password", None)
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")

    result = email_service.send_announcement_with_result(
        "Subject",
        "Body",
        ["recipient@example.com"],
    )

    assert result.error is not None
    assert "SMTP backend requires SMTP_USERNAME and SMTP_PASSWORD." in result.error


def test_send_announcement_with_result_logs_failure(monkeypatch, caplog):
    class BoomSMTP:
        def __init__(self, host, port, timeout=None, context=None):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(email_service.smtplib, "SMTP", BoomSMTP)
    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", "smtp-user")
    monkeypatch.setattr(email_service.settings, "email_host_password", "smtp-pass")
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")

    with caplog.at_level(logging.ERROR):
        result = email_service.send_announcement_with_result(
            "Subject",
            "Body",
            ["recipient@example.com"],
        )

    assert result.error is not None
    assert "RuntimeError: smtp down" in result.error
    assert "backend=smtp error_class=RuntimeError" in caplog.text
