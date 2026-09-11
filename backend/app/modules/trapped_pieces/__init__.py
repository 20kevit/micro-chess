"""Trapped Pieces exercise: select every trapped non-pawn piece."""

from app.modules.exercises import registry
from app.modules.trapped_pieces.scoring import score_squares
from app.modules.trapped_pieces.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_squares)

__all__ = ["SLUG", "validate", "score_squares"]
