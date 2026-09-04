"""Is it Checkmate exercise: classify the side-to-move check state."""

from app.modules.exercises import registry
from app.modules.checkmate.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
