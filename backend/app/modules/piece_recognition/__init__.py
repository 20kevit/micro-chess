"""Piece Recognition exercise: find squares holding the target pieces."""

from app.modules.exercises import registry
from app.modules.piece_recognition.scoring import score_squares
from app.modules.piece_recognition.validator import CANONICAL_TARGETS, SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_squares)

__all__ = ["CANONICAL_TARGETS", "SLUG", "score_squares", "validate"]
