"""Balance Scale exercise: match the right pan's material value."""

from app.modules.exercises import registry
from app.modules.balance_scale.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
