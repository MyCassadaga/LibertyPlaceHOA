from decimal import Decimal

from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
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


def test_calculate_reserve_contribution_clamps_and_rounds():
    result = calculate_reserve_contribution(
        budget_year=2025,
        target_year=2024,
        estimated_cost=Decimal("1000"),
        inflation_rate=Decimal("0.05"),
        current_funding=Decimal("1500"),
    )

    assert result.is_valid_target_year is False
    assert result.years_remaining == 0
    assert result.remaining_needed == Decimal("0")
    assert result.annual_contribution_rounded == Decimal("0.00")

    result = calculate_reserve_contribution(
        budget_year=2025,
        target_year=2030,
        estimated_cost=Decimal("10000"),
        inflation_rate=Decimal("0.02"),
        current_funding=Decimal("1000"),
    )
    assert result.is_valid_target_year is True
    assert result.years_remaining == 5
    assert result.annual_contribution_rounded == Decimal("2008.16")


def test_reserve_crud_upserts_derived_line_items(db_session, create_user):
    user = create_user(email="reserveadmin@example.com", role_name="SYSADMIN")
    client = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db(db_session)

    try:
        app.dependency_overrides[get_current_user] = _override_user(user)
        resp = client.post("/budgets/", json={"year": 2025, "home_count": 1})
        assert resp.status_code == 200
        budget_id = resp.json()["id"]

        reserve_payload = {
            "name": "Roof replacement",
            "target_year": 2030,
            "estimated_cost": "10000",
            "inflation_rate": 0.02,
            "current_funding": "1000",
        }
        resp = client.post(f"/budgets/{budget_id}/reserve-items", json=reserve_payload)
        assert resp.status_code == 200
        reserve_id = resp.json()["id"]

        budget_detail = client.get(f"/budgets/{budget_id}").json()
        assert len(budget_detail["line_items"]) == 1
        derived = budget_detail["line_items"][0]
        assert derived["source_type"] == "RESERVE_PLAN"
        assert derived["source_id"] == reserve_id
        calc = calculate_reserve_contribution(
            budget_year=2025,
            target_year=2030,
            estimated_cost=Decimal("10000"),
            inflation_rate=Decimal("0.02"),
            current_funding=Decimal("1000"),
        )
        assert Decimal(str(derived["amount"])) == calc.annual_contribution_rounded

        update_payload = {"estimated_cost": "12000", "name": "Roof replacement updated"}
        resp = client.patch(f"/budgets/reserve-items/{reserve_id}", json=update_payload)
        assert resp.status_code == 200

        budget_detail = client.get(f"/budgets/{budget_id}").json()
        assert len(budget_detail["line_items"]) == 1
        derived = budget_detail["line_items"][0]
        assert derived["label"] == "Reserve: Roof replacement updated"
        updated_calc = calculate_reserve_contribution(
            budget_year=2025,
            target_year=2030,
            estimated_cost=Decimal("12000"),
            inflation_rate=Decimal("0.02"),
            current_funding=Decimal("1000"),
        )
        assert Decimal(str(derived["amount"])) == updated_calc.annual_contribution_rounded

        resp = client.delete(f"/budgets/reserve-items/{reserve_id}")
        assert resp.status_code == 204

        budget_detail = client.get(f"/budgets/{budget_id}").json()
        assert budget_detail["line_items"] == []
    finally:
        app.dependency_overrides.clear()
        client.close()
