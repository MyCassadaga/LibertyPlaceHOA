from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[override]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation failed.",
                "errors": exc.errors(),
                "path": str(request.url),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[override]
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error.",
                "path": str(request.url),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # type: ignore[override]
        payload: Dict[str, Any] = {"detail": exc.detail or "HTTP error.", "path": str(request.url)}
        if exc.headers:
            payload["headers"] = exc.headers
        return JSONResponse(status_code=exc.status_code, content=payload)
