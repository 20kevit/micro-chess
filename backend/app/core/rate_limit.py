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

    def reset(self) -> None:
        """Clear recorded hits (used by tests to isolate rate-limit windows)."""
        self._hits.clear()


auth_limiter = RateLimiter(per_minute=settings.auth_rate_limit_per_minute)

# Phase 11: user-triggered support writes (ticket + message creation).
support_limiter = RateLimiter(per_minute=settings.support_rate_limit_per_minute)

# Free/Premium verification + coupon abuse protection (same in-memory
# fixed-window mechanism, per-endpoint budgets from Settings).
verification_limiter = RateLimiter(per_minute=settings.verification_rate_limit_per_minute)
billing_limiter = RateLimiter(per_minute=settings.billing_rate_limit_per_minute)
webhook_limiter = RateLimiter(per_minute=settings.webhook_rate_limit_per_minute)


def _client_key(request: Request) -> str:
    if request.client is not None:
        return request.client.host
    return "unknown"


def enforce_auth_rate_limit(request: Request) -> None:
    """Dependency for high-risk auth endpoints (login/register)."""
    if not settings.rate_limit_enabled:
        return
    auth_limiter.check(_client_key(request))


def enforce_support_rate_limit(request: Request) -> None:
    """Dependency for user-triggered support writes (spam protection)."""
    if not settings.rate_limit_enabled:
        return
    support_limiter.check(_client_key(request))


def enforce_verification_rate_limit(request: Request) -> None:
    """Dependency for verification-session creation (code farming)."""
    if not settings.rate_limit_enabled:
        return
    verification_limiter.check(_client_key(request))


def enforce_billing_rate_limit(request: Request) -> None:
    """Dependency for coupon validation/redemption/activation."""
    if not settings.rate_limit_enabled:
        return
    billing_limiter.check(_client_key(request))


def enforce_webhook_rate_limit(request: Request) -> None:
    """Dependency for bot webhooks (pairing-code guessing)."""
    if not settings.rate_limit_enabled:
        return
    webhook_limiter.check(_client_key(request))
