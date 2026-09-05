"""Blindfold Calculation exercise: mate in 1 without seeing the board."""

from app.modules.exercises import registry
from app.modules.blindfold_calculation.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
