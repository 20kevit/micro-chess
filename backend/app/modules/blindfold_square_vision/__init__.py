"""Blindfold Square Vision exercise: minimum moves on an empty board."""

from app.modules.blindfold_square_vision.validator import SLUG, validate
from app.modules.exercises import registry

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
