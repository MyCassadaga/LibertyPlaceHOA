import logging
import re
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import settings
from ..core.request_context import get_request_id

logger = logging.getLogger(__name__)


def _cors_headers_for_request(request: Request) -> Dict[str, str]:
    origin = request.headers.get("origin")
    if not origin:
        return {}
    if origin in settings.cors_allow_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    if settings.cors_allow_origin_regex and re.match(settings.cors_allow_origin_regex, origin):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[override]
        request_id = get_request_id(request)
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation failed.",
                "errors": exc.errors(),
                "path": str(request.url),
                "request_id": request_id,
            },
            headers=_cors_headers_for_request(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[override]
        request_id = get_request_id(request)
        logger.exception(
            "Unhandled exception for request.",
            extra={"request_id": request_id, "path": str(request.url)},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error.",
                "path": str(request.url),
                "request_id": request_id,
            },
            headers=_cors_headers_for_request(request),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # type: ignore[override]
        request_id = get_request_id(request)
        payload: Dict[str, Any] = {
            "detail": exc.detail or "HTTP error.",
            "path": str(request.url),
            "request_id": request_id,
        }
        if exc.headers:
            payload["headers"] = exc.headers
        headers = _cors_headers_for_request(request)
        if exc.headers:
            headers.update(exc.headers)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)
