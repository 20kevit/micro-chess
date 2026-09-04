"""Auth: register / login with JWT. Minimal foundation only."""

from app.modules.auth import router, schemas, service  # noqa: F401

__all__ = ["router", "schemas", "service"]
