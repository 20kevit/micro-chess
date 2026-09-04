"""Get Out of Check exercise: play any legal move that escapes the check."""

from app.modules.exercises import registry
from app.modules.get_out_of_check.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
