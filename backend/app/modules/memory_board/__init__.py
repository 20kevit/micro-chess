"""Memory Board exercise: reconstruct a memorized position exactly."""

from app.modules.exercises import registry
from app.modules.memory_board.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
