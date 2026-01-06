from decimal import Decimal

from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import Budget
from backend.services.reserve_contribution import calculate_reserve_contribution


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


def test_budget_lifecycle(db_session, create_user):
    board_user = create_user(email="boardbudget@example.com", role_name="BOARD")
    board_user_two = create_user(email="boardbudget2@example.com", role_name="BOARD")
    board_user_three = create_user(email="boardbudget3@example.com", role_name="BOARD")
    sysadmin_user = create_user(email="sysbudget@example.com", role_name="SYSADMIN")
    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)

    try:
        app.dependency_overrides[get_current_user] = _override_user(board_user)
        resp = client.post("/budgets/", json={"year": 2026, "home_count": 10})
        assert resp.status_code == 200
        budget_id = resp.json()["id"]

        line_payload = {
            "label": "Legal fees",
            "category": "Operations",
            "amount": "1200",
            "is_reserve": False,
        }
        resp = client.post(f"/budgets/{budget_id}/line-items", json=line_payload)
        assert resp.status_code == 200

        reserve_payload = {
            "name": "Fence replacement",
            "target_year": 2040,
            "estimated_cost": "25000",
            "inflation_rate": 0.03,
            "current_funding": "5000",
        }
        resp = client.post(f"/budgets/{budget_id}/reserve-items", json=reserve_payload)
        assert resp.status_code == 200

        resp = client.post(f"/budgets/{budget_id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_count"] == 1
        assert data["status"] == "DRAFT"

        app.dependency_overrides[get_current_user] = _override_user(board_user_two)
        resp = client.post(f"/budgets/{budget_id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"

        homeowner_user = create_user(email="homebudget@example.com", role_name="HOMEOWNER")
        app.dependency_overrides[get_current_user] = _override_user(homeowner_user)
        resp = client.get("/budgets/")
        assert resp.status_code == 200
        assert any(entry["status"] == "APPROVED" for entry in resp.json())

        resp = client.get(f"/budgets/{budget_id}")
        assert resp.status_code == 200
        data = resp.json()
        reserve_calc = calculate_reserve_contribution(
            budget_year=2026,
            target_year=2040,
            estimated_cost=Decimal("25000"),
            inflation_rate=Decimal("0.03"),
            current_funding=Decimal("5000"),
        )
        expected_total = Decimal("1200.00") + reserve_calc.annual_contribution_rounded
        assert Decimal(str(data["total_annual"])) == expected_total
        assert data["reserve_items"][0]["name"] == "Fence replacement"

        app.dependency_overrides[get_current_user] = _override_user(sysadmin_user)
        resp = client.post(f"/budgets/{budget_id}/unlock")
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRAFT"

        resp = client.post(f"/budgets/{budget_id}/lock")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
    finally:
        app.dependency_overrides.clear()
        client.close()
