from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.config import settings
from backend.main import app
from backend.models.models import Invoice, Notification, OwnerUserLink


def _override_get_db(session):
    def _generator():
        try:
            yield session
        finally:
            pass

    return _generator


def _override_user(user):
    def _provider():
        return user

    return _provider


def _create_overdue_invoice(owner_id, days_overdue):
    due_date = date.today() - timedelta(days=days_overdue)
    return Invoice(
        owner_id=owner_id,
        amount=Decimal("100.00"),
        original_amount=Decimal("100.00"),
        due_date=due_date,
        status="OPEN",
    )


def test_overdue_accounts_list_groups_invoices(db_session, create_user, create_owner):
    board_user = create_user(email="board@example.com", role_name="BOARD")
    owner = create_owner(name="Delinquent", email="delinquent@example.com")
    invoice_one = _create_overdue_invoice(owner.id, 45)
    invoice_two = _create_overdue_invoice(owner.id, 10)
    db_session.add_all([invoice_one, invoice_two])
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)

    client = TestClient(app)
    try:
        response = client.get("/billing/overdue")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        entry = payload[0]
        assert entry["owner_id"] == owner.id
        assert entry["max_months_overdue"] >= 1
        assert len(entry["invoices"]) == 2
        invoice_ids = {item["id"] for item in entry["invoices"]}
        assert invoice_one.id in invoice_ids
        assert invoice_two.id in invoice_ids
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_contact_overdue_owner_notifies_linked_users(db_session, create_user, create_owner):
    board_user = create_user(email="board2@example.com", role_name="BOARD")
    homeowner_user = create_user(email="homeowner@example.com", role_name="HOMEOWNER")
    owner = create_owner(name="Reminder", email="reminder@example.com")
    invoice = _create_overdue_invoice(owner.id, 35)
    db_session.add_all([invoice, OwnerUserLink(owner_id=owner.id, user_id=homeowner_user.id, link_type="PRIMARY")])
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    client = TestClient(app)
    try:
        response = client.post(f"/billing/overdue/{owner.id}/contact", json={"message": "Please pay soon."})
        assert response.status_code == 200
        payload = response.json()
        assert payload["notified_user_ids"] == [homeowner_user.id]
        notes = db_session.query(Notification).filter(Notification.user_id == homeowner_user.id).all()
        assert len(notes) == 1
        assert "Please pay soon." in notes[0].message
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_forward_overdue_owner_generates_packet(tmp_path, db_session, create_user, create_owner, monkeypatch):
    board_user = create_user(email="board3@example.com", role_name="BOARD")
    owner = create_owner(name="Escalate", email="escalate@example.com")
    invoice = _create_overdue_invoice(owner.id, 65)
    db_session.add(invoice)
    db_session.commit()

    output_dir = tmp_path / "pdfs"
    monkeypatch.setattr(settings, "pdf_output_dir", str(output_dir))

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    client = TestClient(app)
    try:
        response = client.post(
            f"/billing/overdue/{owner.id}/forward-attorney",
            json={"notes": "Escalate to counsel."},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "notice_url" in payload
        notice_url = payload["notice_url"]
        assert notice_url
        path = Path(notice_url)
        if not path.is_absolute():
            path = Path.cwd() / notice_url.lstrip("/")
        assert path.exists()
        assert path.suffix == ".pdf"
    finally:
        client.close()
        app.dependency_overrides.clear()
