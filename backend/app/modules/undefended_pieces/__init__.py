"""Undefended Pieces exercise: select every undefended piece on the board."""

from app.modules.exercises import registry
from app.modules.undefended_pieces.scoring import score_squares
from app.modules.undefended_pieces.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_squares)

__all__ = ["SLUG", "score_squares", "validate"]
