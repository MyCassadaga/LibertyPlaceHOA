from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr

from ..auth.jwt import require_roles
from ..config import settings
from ..services import email as email_service
from ..services import system_settings

router = APIRouter()

require_sysadmin = require_roles("SYSADMIN")


class TestEmailRequest(BaseModel):
    recipient: EmailStr
    subject: Optional[str] = "Liberty Place HOA test email"
    body: Optional[str] = "This is a test email from the Liberty Place HOA system."


class TestEmailResponse(BaseModel):
    backend: str
    success: bool
    status_code: Optional[int]
    request_id: Optional[str]
    error: Optional[str]


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


@router.post("/admin/test-email", response_model=TestEmailResponse)
def send_test_email(
    payload: TestEmailRequest,
    _: object = Depends(require_sysadmin),
    admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> TestEmailResponse:
    if not settings.admin_token:
        raise HTTPException(status_code=404, detail="Test email endpoint is disabled.")
    if not admin_token or admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    result = email_service.send_announcement_with_result(
        payload.subject or "Liberty Place HOA test email",
        payload.body or "This is a test email from the Liberty Place HOA system.",
        [payload.recipient],
    )
    return TestEmailResponse(
        backend=result.backend,
        success=result.error is None,
        status_code=result.status_code,
        request_id=result.request_id,
        error=result.error,
    )
