"""Rule of the Square exercise: can the king catch the pawn?."""

from app.modules.exercises import registry
from app.modules.rule_of_the_square.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
