"""Captures exercise: select every enemy piece the hunter can capture."""

from app.modules.exercises import registry
from app.modules.captures.scoring import score_squares
from app.modules.captures.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_squares)

__all__ = ["SLUG", "score_squares", "validate"]
