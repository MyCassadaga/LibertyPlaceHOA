import sys
from types import ModuleType

from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import NoticeType
from backend.services import email as email_service


def _override_get_db(session):
    def _inner():
        try:
            yield session
        finally:
            pass

    return _inner


def _override_user(user):
    def _inner():
        return user

    return _inner


def _install_fake_sendgrid(monkeypatch, sent_messages):
    sendgrid_module = ModuleType("sendgrid")
    helpers_module = ModuleType("sendgrid.helpers")
    mail_module = ModuleType("sendgrid.helpers.mail")

    class Email:
        def __init__(self, email, name=None):
            self.email = email
            self.name = name

    class SandBoxMode:
        def __init__(self, enable=False):
            self.enable = enable

    class MailSettings:
        def __init__(self, sandbox_mode=None):
            self.sandbox_mode = sandbox_mode

    class Mail:
        def __init__(self, from_email, to_emails, subject, plain_text_content):
            self.from_email = from_email
            self.to_emails = to_emails
            self.subject = subject
            self.plain_text_content = plain_text_content
            self.reply_to = None
            self.mail_settings = None

    class SendGridAPIClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def send(self, message):
            sent_messages.append(message)

            class Response:
                status_code = 202
                headers = {"X-Message-Id": "test-message-id"}

            return Response()

    sendgrid_module.SendGridAPIClient = SendGridAPIClient
    mail_module.Email = Email
    mail_module.Mail = Mail
    mail_module.MailSettings = MailSettings
    mail_module.SandBoxMode = SandBoxMode
    sendgrid_module.helpers = helpers_module

    monkeypatch.setitem(sys.modules, "sendgrid", sendgrid_module)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers", helpers_module)
    monkeypatch.setitem(sys.modules, "sendgrid.helpers.mail", mail_module)


def test_sendgrid_announcement_trigger_does_not_write_local_email(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
    tmp_path,
):
    board_user = create_user(email="boardannounce@example.com", role_name="BOARD")
    create_owner(email="announce-owner@example.com")

    sent_messages = []
    _install_fake_sendgrid(monkeypatch, sent_messages)

    output_dir = tmp_path / "emails"
    monkeypatch.setattr(email_service.settings, "email_backend", "sendgrid")
    monkeypatch.setattr(email_service.settings, "sendgrid_api_key", "test-api-key")
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")
    monkeypatch.setattr(email_service.settings, "email_from_name", "Liberty Place HOA")
    monkeypatch.setattr(email_service.settings, "email_reply_to", "reply@example.com")
    monkeypatch.setattr(email_service.settings, "sendgrid_sandbox_mode", True)
    monkeypatch.setattr(email_service.settings, "email_output_dir", str(output_dir))

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        response = client.post(
            "/communications/announcements",
            json={
                "subject": "Announcement",
                "body": "Hello owners",
                "delivery_methods": ["email"],
            },
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message.from_email.email == "no-reply@example.com"
    assert message.from_email.name == "Liberty Place HOA"
    assert message.reply_to.email == "reply@example.com"
    assert message.subject
    assert message.plain_text_content
    assert message.mail_settings.sandbox_mode.enable is True
    assert not output_dir.exists()


def test_sendgrid_notice_trigger_does_not_write_local_email(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
    tmp_path,
):
    board_user = create_user(email="boardnotice@example.com", role_name="BOARD")
    owner = create_owner(email="notice-owner@example.com")
    owner.primary_email = "notice-owner@example.com"
    db_session.add(owner)

    notice_type = db_session.query(NoticeType).filter_by(code="DELINQUENCY_FIRST").first()
    if not notice_type:
        notice_type = NoticeType(
            code="DELINQUENCY_FIRST",
            name="Delinquency",
            allow_electronic=True,
            requires_paper=False,
            default_delivery="EMAIL_ONLY",
        )
        db_session.add(notice_type)
        db_session.commit()

    sent_messages = []
    _install_fake_sendgrid(monkeypatch, sent_messages)

    output_dir = tmp_path / "emails"
    monkeypatch.setattr(email_service.settings, "email_backend", "sendgrid")
    monkeypatch.setattr(email_service.settings, "sendgrid_api_key", "test-api-key")
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")
    monkeypatch.setattr(email_service.settings, "email_from_name", "Liberty Place HOA")
    monkeypatch.setattr(email_service.settings, "email_reply_to", "reply@example.com")
    monkeypatch.setattr(email_service.settings, "sendgrid_sandbox_mode", False)
    monkeypatch.setattr(email_service.settings, "email_output_dir", str(output_dir))

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        response = client.post(
            "/notices/",
            json={
                "owner_id": owner.id,
                "notice_type_code": "DELINQUENCY_FIRST",
                "subject": "Delinquent",
                "body_html": "<p>Pay now</p>",
            },
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message.from_email.email == "no-reply@example.com"
    assert message.from_email.name == "Liberty Place HOA"
    assert message.reply_to.email == "reply@example.com"
    assert message.subject
    assert message.plain_text_content
    assert not output_dir.exists()
