"""Get Out of Check exercise: find every legal move that escapes the check."""

from app.modules.exercises import registry
from app.modules.get_out_of_check.scoring import score_moves
from app.modules.get_out_of_check.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_moves)

__all__ = ["SLUG", "score_moves", "validate"]
