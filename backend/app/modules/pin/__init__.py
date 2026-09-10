"""Pin exercise: identify the three pieces forming a pin, in order."""

from app.modules.exercises import registry
from app.modules.pin.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
