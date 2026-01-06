import uuid
from typing import Optional

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


def assign_request_id(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER) or request.headers.get(CORRELATION_ID_HEADER)
    if not request_id:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    return request_id


def get_request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)
