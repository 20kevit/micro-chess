"""Abuse-protection hooks: in-memory fixed-window rate limiting.

Centralized integration point (see docs/platform/SECURITY.md sections
13/68). Limits live in Settings, never hard-coded in handlers.

Single-process memory only — sufficient for the current monolith.
Distributed limiting would be premature infrastructure; revisit only
with demonstrated multi-instance need.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import settings


class RateLimiter:
    def __init__(self, *, per_minute: int, clock=time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = self._clock()
        window_start = now - 60.0
        recent = [t for t in self._hits[key] if t > window_start]
        self._hits[key] = recent
        if len(recent) >= self.per_minute:
            return False
        recent.append(now)
        return True

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited")


auth_limiter = RateLimiter(per_minute=settings.auth_rate_limit_per_minute)


def _client_key(request: Request) -> str:
    if request.client is not None:
        return request.client.host
    return "unknown"


def enforce_auth_rate_limit(request: Request) -> None:
    """Dependency for high-risk auth endpoints (login/register)."""
    if not settings.rate_limit_enabled:
        return
    auth_limiter.check(_client_key(request))
