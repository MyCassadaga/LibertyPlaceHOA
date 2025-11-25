from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth.jwt import require_roles
from ..config import settings
from ..services import system_settings

router = APIRouter()

require_sysadmin = require_roles("SYSADMIN")


@router.get("/login-background")
def get_login_background() -> dict[str, str | None]:
    url = system_settings.get_login_background_url()
    return {"url": url}


@router.post("/login-background", status_code=201)
async def upload_login_background(
    file: UploadFile = File(...),
    _: object = Depends(require_sysadmin),
) -> dict[str, str | None]:
    if file.content_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(status_code=400, detail="Upload a PNG or JPG image.")

    contents = await file.read()
    try:
        url = system_settings.save_login_background(contents, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"url": url}


@router.get("/runtime", dependencies=[Depends(require_sysadmin)])
def get_runtime_diagnostics() -> Dict[str, Any]:
    """Expose non-sensitive runtime settings for debugging."""
    return {
        "email_backend": settings.email_backend,
        "email_host": settings.email_host,
        "email_port": settings.email_port,
        "email_use_tls": settings.email_use_tls,
        "file_storage_backend": settings.file_storage_backend,
        "uploads_public_url": settings.uploads_public_url,
        "click2mail_enabled": settings.click2mail_enabled,
        "api_base_url": str(settings.api_base_url),
        "frontend_url": str(settings.frontend_url),
    }
