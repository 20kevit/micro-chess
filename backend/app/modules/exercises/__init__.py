"""Exercise schemas and catalog routes."""

from app.modules.exercises import models, registry, router, schemas  # noqa: F401

__all__ = ["models", "registry", "router", "schemas"]
