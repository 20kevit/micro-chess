"""Captures exercise: select every enemy piece the hunter can capture."""

from app.modules.exercises import registry
from app.modules.captures.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
