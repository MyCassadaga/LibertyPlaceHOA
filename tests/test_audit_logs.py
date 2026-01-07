from fastapi.testclient import TestClient

from sqlalchemy.orm import sessionmaker

from backend.api.dependencies import get_db
from backend.auth.jwt import create_refresh_token
from backend.auth.jwt import get_current_user
from backend.main import app
import backend.main as app_main
from backend.models.models import AuditLog


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


def test_register_writes_audit_log(db_session, create_user):
    """SYSADMIN user creation should emit an audit_log row."""
    sysadmin = create_user(email="admin@example.com", role_name="SYSADMIN")
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(sysadmin)
    client = TestClient(app)

    try:
        payload = {
            "email": "new.user@example.com",
            "full_name": "New User",
            "password": "changeme123",
            "role_ids": [sysadmin.primary_role.id],
        }
        response = client.post("/auth/register", json=payload)
        assert response.status_code == 200

        logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "user.register", AuditLog.target_entity_type == "User")
            .all()
        )
        assert len(logs) == 1
        entry = logs[0]
        assert entry.actor_user_id == sysadmin.id
        assert "new.user@example.com" in (entry.after or "")
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_refresh_audit_log_allows_missing_user(db_session):
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    original_session_local = app_main.SessionLocal
    app_main.SessionLocal = sessionmaker(bind=db_session.bind)
    client = TestClient(app)

    try:
        refresh_token = create_refresh_token("1")
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 401

        logs = db_session.query(AuditLog).filter(AuditLog.action == "POST /auth/refresh").all()
        assert len(logs) == 1
        entry = logs[0]
        assert entry.actor_user_id is None
        assert "\"status\": 401" in (entry.after or "")
    finally:
        client.close()
        app.dependency_overrides.clear()
        app_main.SessionLocal = original_session_local
