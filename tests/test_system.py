import base64
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.system import require_sysadmin
from backend.services import system_settings
from backend.services.storage import storage_service


def _override_sysadmin():
    class Dummy:
        id = 1

    return Dummy()


def test_login_background_get_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(system_settings, "SYSTEM_DIR", tmp_path)
    monkeypatch.setattr(storage_service, "upload_root", tmp_path)

    client = TestClient(app)
    response = client.get("/system/login-background")
    assert response.status_code == 200
    assert response.json() == {"url": None}


def test_login_background_upload_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(system_settings, "SYSTEM_DIR", tmp_path)
    monkeypatch.setattr(storage_service, "upload_root", tmp_path)

    client = TestClient(app)
    app.dependency_overrides[require_sysadmin] = _override_sysadmin

    try:
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
        files = {"file": ("background.png", png_bytes, "image/png")}
        upload_response = client.post("/system/login-background", files=files)
        assert upload_response.status_code == 201
        data = upload_response.json()
        assert data["url"] == "/uploads/system/login-bg.png"
        stored_file = tmp_path / "system" / "login-bg.png"
        assert stored_file.exists()

        get_response = client.get("/system/login-background")
        assert get_response.status_code == 200
        assert get_response.json() == {"url": "/uploads/system/login-bg.png"}
    finally:
        app.dependency_overrides.pop(require_sysadmin, None)
