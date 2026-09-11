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

_LOG_FORMAT = "%(asctime)s %(levelname)s [req=%(microchess_request_id)s] %(name)s: %(message)s"


class RequestIdFormatter(logging.Formatter):
    """Fills the request id from context, defaulting to "-" outside requests."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "microchess_request_id"):
            record.microchess_request_id = request_id_var.get()  # type: ignore[attr-defined]
        return super().format(record)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        # Host (tests, uvicorn workers with preset logging) owns handlers;
        # request ids still propagate via the middleware context var.
        return
    handler = logging.StreamHandler()
    handler.setFormatter(RequestIdFormatter(_LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


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
