"""Pin exercise: play any legal move that creates a classical pin."""

from app.modules.exercises import registry
from app.modules.pin.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
