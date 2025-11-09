import json
from pathlib import Path
from typing import Dict, Optional, Union

from ..config import settings
from .storage import storage_service

SYSTEM_DIR = settings.uploads_root_path / "system"
LOGIN_BACKGROUND_KEY = "login_background"
LOGIN_BACKGROUND_BASENAME = "login-bg"
ALLOWED_EXTENSIONS = {".png", ".jpg"}


def _ensure_system_dir() -> Path:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    return SYSTEM_DIR


def _settings_path() -> Path:
    return _ensure_system_dir() / "settings.json"


def _read_settings() -> Dict[str, Union[str, dict]]:
    settings_file = _settings_path()
    if not settings_file.exists():
        return {}
    try:
        return json.loads(settings_file.read_text())
    except json.JSONDecodeError:
        return {}


def _write_settings(data: Dict[str, Union[str, dict]]) -> None:
    settings_file = _settings_path()
    settings_file.write_text(json.dumps(data, indent=2))


def _normalize_entry(entry: Union[str, Dict[str, str]]) -> Dict[str, str]:
    if isinstance(entry, dict):
        return {
            "relative": entry.get("relative") or entry.get("path") or "",
            "public": entry.get("public") or entry.get("public_path") or entry.get("url") or "",
        }
    return {"relative": entry, "public": entry}


def get_login_background_url() -> Optional[str]:
    settings_data = _read_settings()
    stored = settings_data.get(LOGIN_BACKGROUND_KEY)
    if not stored:
        return None
    normalized = _normalize_entry(stored)
    public = normalized.get("public")
    if not public:
        return None
    if public.startswith("http"):
        return public
    return f"/{public.lstrip('/')}"


def save_login_background(contents: bytes, original_filename: str) -> str:
    ext = Path(original_filename or "").suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload a PNG or JPG image.")

    stored = storage_service.save_file(
        f"system/{LOGIN_BACKGROUND_BASENAME}{ext}",
        contents,
        content_type="image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png",
    )

    settings_data = _read_settings()
    previous = settings_data.get(LOGIN_BACKGROUND_KEY)
    if previous:
        normalized = _normalize_entry(previous)
        if normalized.get("relative"):
            storage_service.delete_file(normalized["relative"])

    payload = {"relative": stored.relative_path, "public": stored.public_path}
    settings_data[LOGIN_BACKGROUND_KEY] = payload
    _write_settings(settings_data)

    public = stored.public_path
    if public.startswith("http"):
        return public
    return f"/{public.lstrip('/')}"
