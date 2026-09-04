"""Hanging Pieces exercise: select every hanging piece on the board."""

from app.modules.exercises import registry
from app.modules.hanging_pieces.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
