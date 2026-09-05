"""Piece Recognition exercise: find squares holding the target pieces."""

from app.modules.exercises import registry
from app.modules.piece_recognition.validator import CANONICAL_TARGETS, SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["CANONICAL_TARGETS", "SLUG", "validate"]
