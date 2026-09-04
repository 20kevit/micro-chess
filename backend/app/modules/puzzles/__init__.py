"""Puzzles: one concrete question/task per exercise."""

from app.modules.puzzles import models, router, schemas, service  # noqa: F401

__all__ = ["models", "router", "schemas", "service"]
