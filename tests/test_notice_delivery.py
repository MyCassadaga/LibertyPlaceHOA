from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import NoticeType, Owner, PaperworkItem
from backend.services.notices import resolve_delivery


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


def test_resolve_delivery_rules(db_session, create_owner):
    owner = create_owner()
    owner.primary_email = "owner@example.com"
    owner.delivery_preference_global = "AUTO"
    db_session.add(owner)

    notice_type = NoticeType(
        code="TEST",
        name="Test",
        allow_electronic=True,
        requires_paper=False,
        default_delivery="AUTO",
    )
    db_session.add(notice_type)
    db_session.commit()

    assert resolve_delivery(owner, notice_type) == "EMAIL"

    notice_type.requires_paper = True
    assert resolve_delivery(owner, notice_type) == "PAPER"

    owner.delivery_preference_global = "PAPER_ALL"
    notice_type.requires_paper = False
    assert resolve_delivery(owner, notice_type) == "PAPER"

    owner.delivery_preference_global = "AUTO"
    owner.primary_email = None
    assert resolve_delivery(owner, notice_type) == "PAPER"


def test_notice_creation_and_paperwork_flow(db_session, create_user, create_owner, monkeypatch):
    board_user = create_user(email="boardnotice@example.com", role_name="BOARD")
    owner = create_owner(email="noticeowner@example.com")
    owner.primary_email = "noticeowner@example.com"
    db_session.add(owner)

    notice_type = db_session.query(NoticeType).filter_by(code="DELINQUENCY_FIRST").first()
    if not notice_type:
        notice_type = NoticeType(
            code="DELINQUENCY_FIRST",
            name="Delinquency",
            allow_electronic=True,
            requires_paper=True,
            default_delivery="AUTO",
        )
        db_session.add(notice_type)
        db_session.commit()

    sent_emails = []

    def fake_send(email, subject, body):
        sent_emails.append((email, subject))

    monkeypatch.setattr("backend.services.email.send_notice_email", fake_send)

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        resp = client.post(
            "/notices/",
            json={
                "owner_id": owner.id,
                "notice_type_code": "DELINQUENCY_FIRST",
                "subject": "Delinquent",
                "body_html": "<p>Pay now</p>",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_channel"] in ("PAPER", "EMAIL_AND_PAPER")
        paperwork = db_session.query(PaperworkItem).first()
        assert paperwork is not None

        resp = client.get("/paperwork/")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1

        paperwork_id = items[0]["id"]

        resp = client.post(f"/paperwork/{paperwork_id}/claim")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CLAIMED"

        resp = client.post(f"/paperwork/{paperwork_id}/mail")
        assert resp.status_code == 200
        assert resp.json()["status"] == "MAILED"
        db_session.refresh(paperwork)
        assert paperwork.pdf_path
        resp = client.get(f"/paperwork/{paperwork_id}/download")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_click2mail_dispatch_requires_config(db_session, create_user, create_owner, monkeypatch):
    board_user = create_user(email="boardnotice2@example.com", role_name="BOARD")
    owner = create_owner(email="noticeowner2@example.com")
    owner.primary_email = "noticeowner2@example.com"
    owner.mailing_address = "123 Main St, Portland, OR 97201"
    db_session.add(owner)

    notice_type = db_session.query(NoticeType).filter_by(code="DELINQUENCY_FIRST").first()
    if not notice_type:
        notice_type = NoticeType(
            code="DELINQUENCY_FIRST",
            name="Delinquency",
            allow_electronic=True,
            requires_paper=True,
            default_delivery="AUTO",
        )
        db_session.add(notice_type)
        db_session.commit()

    sent_emails = []

    def fake_send(email, subject, body):
        sent_emails.append((email, subject))

    monkeypatch.setattr("backend.services.email.send_notice_email", fake_send)

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        resp = client.post(
            "/notices/",
            json={
                "owner_id": owner.id,
                "notice_type_code": "DELINQUENCY_FIRST",
                "subject": "Delinquent",
                "body_html": "<p>Pay now</p>",
            },
        )
        assert resp.status_code == 200
        paperwork = db_session.query(PaperworkItem).first()
        assert paperwork is not None

        resp = client.post(f"/paperwork/{paperwork.id}/dispatch-click2mail")
        assert resp.status_code == 400
        assert "Click2Mail integration is not configured" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        client.close()
