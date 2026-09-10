"""Reverse Opening exercise: rebuild the opening from move one."""

from app.modules.exercises import registry
from app.modules.reverse_opening.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
