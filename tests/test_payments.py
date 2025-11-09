from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import Contract, OwnerUserLink


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


def test_create_payment_session_returns_mock_url():
    client = TestClient(app)
    response = client.post("/payments/session", json={"invoiceId": 123})
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"checkoutUrl": "/billing?mock-payment-success=true"}


def test_autopay_enrollment_flow(db_session, create_user, create_owner):
    homeowner = create_user(email="autopay@example.com", role_name="HOMEOWNER")
    owner = create_owner(email=homeowner.email)
    link = OwnerUserLink(owner_id=owner.id, user_id=homeowner.id)
    db_session.add(link)
    db_session.commit()

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(homeowner)
    try:
        resp = client.get("/payments/autopay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "NOT_ENROLLED"

        resp = client.post("/payments/autopay", json={"payment_day": 5, "amount_type": "STATEMENT_BALANCE"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["payment_day"] == 5

        resp = client.delete("/payments/autopay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_vendor_payment_workflow(db_session, create_user):
    from datetime import date

    board_user = create_user(email="boardpayments@example.com", role_name="BOARD")
    contract = Contract(
        vendor_name="ACME Landscaping",
        service_type="Landscaping",
        start_date=date(2025, 1, 1),
        end_date=None,
        auto_renew=True,
    )
    db_session.add(contract)
    db_session.commit()

    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(board_user)
    try:
        resp = client.post("/payments/vendors", json={"contract_id": contract.id, "amount": "250.00"})
        assert resp.status_code == 200
        payment_id = resp.json()["id"]
        assert resp.json()["status"] == "PENDING"

        resp = client.post(f"/payments/vendors/{payment_id}/send")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUBMITTED"

        resp = client.post(f"/payments/vendors/{payment_id}/mark-paid")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAID"
    finally:
        app.dependency_overrides.clear()
        client.close()
