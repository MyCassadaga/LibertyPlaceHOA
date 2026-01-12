from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.seeds.template_types import ensure_template_types


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


def test_template_types_includes_billing_notice(db_session, create_user):
    ensure_template_types(db_session)
    sysadmin = create_user(email="sysadmin@example.com", role_name="SYSADMIN")
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(sysadmin)
    client = TestClient(app)

    try:
        response = client.get("/templates/types")
        assert response.status_code == 200
        payload = response.json()
        assert any(
            entry["key"] == "billing_notice"
            and entry["label"] == "Billing Notice"
            and entry["definition"] == "Emails sent to individuals as a result of billing."
            for entry in payload
        )
    finally:
        client.close()
        app.dependency_overrides.clear()
