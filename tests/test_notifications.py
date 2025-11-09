from fastapi.testclient import TestClient

from backend.api.dependencies import get_db
from backend.auth.jwt import get_current_user
from backend.main import app
from backend.models.models import Notification


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


def test_list_notifications_returns_only_current_user_items(db_session, create_user):
    user = create_user(email="notify@example.com")
    other = create_user(email="other@example.com")
    note_one = Notification(user_id=user.id, title="Test", message="Body", level="info")
    note_two = Notification(user_id=user.id, title="Another", message="Body", level="info")
    note_other = Notification(user_id=other.id, title="Hidden", message="Body", level="info")
    db_session.add_all([note_one, note_two, note_other])
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    try:
        response = client.get("/notifications/")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        returned_ids = {item["id"] for item in payload}
        assert note_one.id in returned_ids
        assert note_two.id in returned_ids
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_mark_notification_read_sets_timestamp(db_session, create_user):
    user = create_user(email="notify2@example.com")
    notification = Notification(user_id=user.id, title="Unread", message="Body", level="info")
    db_session.add(notification)
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    try:
        response = client.post(f"/notifications/{notification.id}/read")
        assert response.status_code == 200
        data = response.json()
        assert data["read_at"] is not None
        db_session.refresh(notification)
        assert notification.read_at is not None
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_mark_all_notifications_read_updates_multiple_entries(db_session, create_user):
    user = create_user(email="notify3@example.com")
    first = Notification(user_id=user.id, title="First", message="Body", level="info")
    second = Notification(user_id=user.id, title="Second", message="Body", level="info")
    db_session.add_all([first, second])
    db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    app.dependency_overrides[get_current_user] = _override_user(user)
    client = TestClient(app)
    try:
        response = client.post("/notifications/read-all")
        assert response.status_code == 200
        assert response.json()["updated"] == 2
        db_session.refresh(first)
        db_session.refresh(second)
        assert first.read_at is not None
        assert second.read_at is not None
    finally:
        client.close()
        app.dependency_overrides.clear()
