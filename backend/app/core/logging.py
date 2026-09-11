"""Basic observability: logging setup plus request-id propagation.

Plain stdlib logging (no vendor). Every request gets an ``X-Request-ID``
which is echoed back to the caller and attached to error/audit logs so
failures can be correlated without exposing internals.
"""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("microchess_request_id", default="-")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [req=%(microchess_request_id)s] %(name)s: %(message)s",
        defaults={"microchess_request_id": "-"},
    )


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.microchess_request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


def attach_request_id_filter() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, _RequestIdFilter) for f in root.filters):
        root.addFilter(_RequestIdFilter())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        request_id = incoming.strip() if incoming and incoming.strip() else uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response
