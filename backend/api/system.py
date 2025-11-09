from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth.jwt import require_roles
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
