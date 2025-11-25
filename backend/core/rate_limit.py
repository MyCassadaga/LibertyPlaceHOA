import asyncio
import time
from collections import deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import Depends, HTTPException, Request, status


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window: int) -> Tuple[bool, float]:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(0.0, window - (now - bucket[0]))
                return False, retry_after
            bucket.append(now)
            return True, 0.0


_limiter = RateLimiter()


def rate_limit_dependency(scope: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    async def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "anonymous"
        key = f"{scope}:{client_ip}"
        allowed, retry_after = await _limiter.hit(key, limit, window_seconds)
        if not allowed:
            headers = {"Retry-After": str(int(retry_after) or window_seconds)}
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests.", headers=headers)

    return dependency
