"""Player platform: profile, external chess identities, history, progress."""

from app.modules.player import router, schemas, service  # noqa: F401

__all__ = ["router", "schemas", "service"]
