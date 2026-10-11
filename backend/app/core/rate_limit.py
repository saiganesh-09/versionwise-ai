"""In-memory sliding-window rate limiting + security headers.

Single-process limiter — sufficient for single-instance deployments. For
multi-replica production, swap for Redis-backed (e.g. slowapi + redis) while
keeping the same bucket policy. Limits are read from settings per-request so
tests can override them.

Bucket policy:
- auth endpoints (login/register): tight — credential brute-force surface
- chat POST: moderate — each call may hit a paid LLM
- everything else: generous floor
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings


class _SlidingWindow:
    def __init__(self) -> None:
        self.hits: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self.lock:
            calls = self.hits[key]
            self.hits[key] = calls = [t for t in calls if now - t < window_s]
            if len(calls) >= limit:
                return False
            calls.append(now)
            return True


def _bucket_for(request: Request) -> tuple[str, int]:
    path = request.url.path
    settings = get_settings()
    if path.endswith(("/auth/login", "/auth/register")):
        return "auth", settings.auth_rate_limit_per_minute
    if request.method == "POST" and path.endswith("/chat"):
        return "chat", settings.chat_rate_limit_per_minute
    return "general", settings.rate_limit_per_minute


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._windows = _SlidingWindow()

    async def dispatch(self, request: Request, call_next):
        bucket, limit = _bucket_for(request)
        client_ip = request.client.host if request.client else "unknown"
        if not self._windows.allow(f"{bucket}:{client_ip}", limit, 60):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests — slow down and retry.",
                    }
                },
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline headers for API responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        path = request.url.path
        if path.endswith(("/auth/login", "/auth/register", "/chat")):
            # Tokens and answers must not be cached anywhere.
            response.headers["Cache-Control"] = "no-store"
        return response
