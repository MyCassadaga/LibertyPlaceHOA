import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach common security headers to every response."""

    def __init__(
        self,
        app,
        *,
        enable_hsts: bool = True,
        csp: Optional[str] = None,
    ) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.csp = csp

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        headers = response.headers

        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.enable_hsts and request.url.scheme == "https":
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if self.csp:
            headers.setdefault("Content-Security-Policy", self.csp)

        return response


def log_security_warnings(jwt_secret: str, email_backend: str, stripe_api_key: Optional[str]) -> None:
    if jwt_secret == "dev-secret-please-change":
        logger.warning("JWT secret is using the insecure default; set JWT_SECRET in the environment.")
    backend_normalized = (email_backend or "local").lower().strip()
    if backend_normalized == "local":
        logger.warning("Email backend is set to local stub; production email will not be delivered.")
    if not stripe_api_key or stripe_api_key.startswith("mk_"):
        logger.warning("Stripe API key is missing or using mock key; live payments will be disabled.")
