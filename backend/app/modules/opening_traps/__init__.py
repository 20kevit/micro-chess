"""Opening Traps exercise: find the tactic, eyes closed."""

from app.modules.exercises import registry
from app.modules.opening_traps.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
