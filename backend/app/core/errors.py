"""Centralized API error contract.

Target shape (see docs/platform/API_CONTRACTS.md section 53)::

    {"error": {"code": "PUZZLE_NOT_AVAILABLE", "message": "...", "details": {}}}

``code`` is a stable machine-readable token, ``message`` is safe
explanatory text, ``details`` carries structured validation info when
safe. Responses never include stack traces, SQL, paths, or secrets.

Backward compatibility: existing clients read the legacy ``detail``
field, so every handler below also preserves it alongside the new
``error`` envelope. New code should read ``error.code``.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("microchess.errors")

# Literal 422: avoids the renamed Starlette constant across versions.
HTTP_422 = 422


def _code_for_detail(detail: object, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        candidate = detail.strip().upper()
        if candidate and all(ch.isalnum() or ch == "_" for ch in candidate):
            return candidate
    return fallback


def error_body(
    *,
    code: str,
    message: str,
    details: dict | None = None,
    legacy_detail: object = None,
    include_legacy: bool = True,
) -> dict:
    body: dict = {"error": {"code": code, "message": message, "details": details or {}}}
    if include_legacy and legacy_detail is not None:
        body["detail"] = legacy_detail
    return body


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    _ = request
    code = _code_for_detail(exc.detail, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code=code, message=message, legacy_detail=exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    _ = request
    safe_errors = [
        {"loc": list(err.get("loc", [])), "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=HTTP_422,
        content=error_body(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": safe_errors},
            legacy_detail=safe_errors,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
    _ = exc
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(
            code="INTERNAL_ERROR",
            message="Unexpected server error.",
            legacy_detail="internal_error",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.exception_handler(StarletteHTTPException)(http_exception_handler)
    app.exception_handler(RequestValidationError)(validation_exception_handler)
    app.exception_handler(Exception)(unhandled_exception_handler)
