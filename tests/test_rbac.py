from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user, require_roles


class DummyUser:
    def __init__(self, *roles: str):
        self._roles = set(roles)

    def has_any_role(self, *role_names: str) -> bool:
        return any(role in self._roles for role in role_names)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/admin")
    def admin_route(_: object = Depends(require_roles("SYSADMIN"))):
        return {"ok": True}

    @app.get("/reports")
    def reports_route(_: object = Depends(require_roles("BOARD", "SYSADMIN"))):
        return {"ok": True}

    return app


def test_admin_route_requires_sysadmin_role():
    app = _build_app()
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: DummyUser("HOMEOWNER")
    response = client.get("/admin")
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: DummyUser("SYSADMIN")
    response = client.get("/admin")
    assert response.status_code == 200


def test_reports_route_allows_board_or_sysadmin():
    app = _build_app()
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: DummyUser("HOMEOWNER")
    response = client.get("/reports")
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: DummyUser("BOARD")
    response = client.get("/reports")
    assert response.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: DummyUser("SYSADMIN")
    response = client.get("/reports")
    assert response.status_code == 200
