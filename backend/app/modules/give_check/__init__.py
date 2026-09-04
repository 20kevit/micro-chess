"""Give Check exercise: play any legal move that checks the opponent king."""

from app.modules.exercises import registry
from app.modules.give_check.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
