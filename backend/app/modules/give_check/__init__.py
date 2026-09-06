"""Giving Check exercise: find every legal move that checks the enemy king."""

from app.modules.exercises import registry
from app.modules.give_check.scoring import score_moves
from app.modules.give_check.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_moves)

__all__ = ["SLUG", "score_moves", "validate"]
