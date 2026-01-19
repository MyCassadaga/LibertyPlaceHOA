from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.api import comms as comms_api
from backend.main import app
from backend.models.models import AuditLog, CommunicationMessage, NoticeType
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


def _install_fake_smtp(monkeypatch, sent_messages):
    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.logged_in = None
            self.started_tls = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            self.started_tls = True
            return None

        def login(self, username, password):
            self.logged_in = (username, password)
            return None

        def send_message(self, message):
            sent_messages.append(message)
            return {}

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)


def test_smtp_announcement_trigger_does_not_write_local_email(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
    tmp_path,
):
    board_user = create_user(email="boardannounce@example.com", role_name="BOARD")
    create_owner(email="announce-owner@example.com")

    sent_messages = []
    _install_fake_smtp(monkeypatch, sent_messages)

    output_dir = tmp_path / "emails"
    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", "smtp-user")
    monkeypatch.setattr(email_service.settings, "email_host_password", "smtp-pass")
    monkeypatch.setattr(email_service.settings, "email_use_tls", True)
    monkeypatch.setattr(email_service.settings, "email_use_ssl", False)
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")
    monkeypatch.setattr(email_service.settings, "email_from_name", "Liberty Place HOA")
    monkeypatch.setattr(email_service.settings, "email_reply_to", "reply@example.com")
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
    assert message["From"] == "Liberty Place HOA <no-reply@example.com>"
    assert message["To"] == "announce-owner@example.com"
    assert message["Reply-To"] == "reply@example.com"
    assert message["Subject"]
    assert "Hello owners" in message.get_payload()
    assert not output_dir.exists()


def test_smtp_notice_trigger_does_not_write_local_email(
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
    _install_fake_smtp(monkeypatch, sent_messages)

    output_dir = tmp_path / "emails"
    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host", "smtp.gmail.com")
    monkeypatch.setattr(email_service.settings, "email_host_user", "smtp-user")
    monkeypatch.setattr(email_service.settings, "email_host_password", "smtp-pass")
    monkeypatch.setattr(email_service.settings, "email_use_tls", True)
    monkeypatch.setattr(email_service.settings, "email_use_ssl", False)
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")
    monkeypatch.setattr(email_service.settings, "email_from_name", "Liberty Place HOA")
    monkeypatch.setattr(email_service.settings, "email_reply_to", "reply@example.com")
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
    assert message["From"] == "Liberty Place HOA <no-reply@example.com>"
    assert message["To"] == "notice-owner@example.com"
    assert message["Reply-To"] == "reply@example.com"
    assert message["Subject"]
    assert "Pay now" in message.get_payload()
    assert not output_dir.exists()


def test_communication_message_email_tracks_success(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
    tmp_path,
):
    board_user = create_user(email="boardmessage@example.com", role_name="BOARD")
    create_owner(email="message-owner@example.com")

    output_dir = tmp_path / "emails"
    monkeypatch.setattr(email_service.settings, "email_backend", "local")
    monkeypatch.setattr(email_service.settings, "email_output_dir", str(output_dir))

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        response = client.post(
            "/communications/messages",
            json={
                "message_type": "ANNOUNCEMENT",
                "subject": "Update",
                "body": "Email body",
                "delivery_methods": ["email"],
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()
        client.close()

    db_session.expire_all()
    message = db_session.query(CommunicationMessage).first()
    assert message is not None
    assert message.email_delivery_status == "SENT"
    assert message.email_queued_at is not None
    assert message.email_send_attempted_at is not None
    assert message.email_sent_at is not None
    assert message.email_failed_at is None
    assert message.email_last_error is None
    assert message.email_provider_status_code == 200

    audits = db_session.query(AuditLog).filter_by(action="communications.email.sent").all()
    assert audits


def test_communication_message_email_records_failure(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
):
    board_user = create_user(email="boardmessagefail@example.com", role_name="BOARD")
    create_owner(email="message-fail-owner@example.com")

    def _fake_send(*_args, **_kwargs):
        return email_service.SendResult(
            backend="test",
            status_code=503,
            request_id=None,
            error="Provider error",
        )

    monkeypatch.setattr(email_service, "send_announcement_with_result", _fake_send)

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        response = client.post(
            "/communications/messages",
            json={
                "message_type": "ANNOUNCEMENT",
                "subject": "Update",
                "body": "Email body",
                "delivery_methods": ["email"],
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()
        client.close()

    db_session.expire_all()
    message = db_session.query(CommunicationMessage).first()
    assert message is not None
    assert message.email_delivery_status == "FAILED"
    assert message.email_queued_at is not None
    assert message.email_send_attempted_at is not None
    assert message.email_sent_at is None
    assert message.email_failed_at is not None
    assert message.email_last_error == "Provider error"
    assert message.email_provider_status_code == 503

    audits = db_session.query(AuditLog).filter_by(action="communications.email.failed").all()
    assert audits


def test_communication_message_email_background_task_transitions_attempted(
    db_session,
    create_user,
    monkeypatch,
):
    board_user = create_user(email="boarddirect@example.com", role_name="BOARD")

    message = CommunicationMessage(
        message_type="ANNOUNCEMENT",
        subject="Direct",
        body="Direct body",
        delivery_methods=["email"],
        recipient_snapshot=[],
        recipient_count=1,
        created_by_user_id=board_user.id,
    )
    message.email_delivery_status = "QUEUED"
    db_session.add(message)
    db_session.commit()

    monkeypatch.setattr(email_service.settings, "email_backend", "local")

    session_factory = sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)
    comms_api._send_message_email(
        session_factory,
        message.id,
        "Direct",
        "Direct body",
        ["owner@example.com"],
        board_user.id,
        "test-request-id",
    )

    db_session.expire_all()
    updated = db_session.query(CommunicationMessage).filter_by(id=message.id).first()
    assert updated.email_delivery_status == "SENT"
    assert updated.email_send_attempted_at is not None
    assert updated.email_sent_at is not None
    assert updated.email_failed_at is None
    assert updated.email_last_error is None


def test_communication_message_email_missing_smtp_credentials_marks_failed(
    db_session,
    create_owner,
    create_user,
    monkeypatch,
):
    board_user = create_user(email="boardmissing@example.com", role_name="BOARD")
    create_owner(email="missing-owner@example.com")

    monkeypatch.setattr(email_service.settings, "email_backend", "smtp")
    monkeypatch.setattr(email_service.settings, "email_host_user", None)
    monkeypatch.setattr(email_service.settings, "email_host_password", None)
    monkeypatch.setattr(email_service.settings, "email_from_address", "no-reply@example.com")

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        response = client.post(
            "/communications/messages",
            json={
                "message_type": "ANNOUNCEMENT",
                "subject": "Missing Key",
                "body": "Email body",
                "delivery_methods": ["email"],
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()
        client.close()

    db_session.expire_all()
    message = db_session.query(CommunicationMessage).first()
    assert message.email_delivery_status == "FAILED"
    assert message.email_failed_at is not None
    assert message.email_last_error
    assert "SMTP_USERNAME" in message.email_last_error
