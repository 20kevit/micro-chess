"""Legal Destinations exercise: select all legal destinations of a target piece."""

from app.modules.exercises import registry
from app.modules.legal_destinations.scoring import score_squares
from app.modules.legal_destinations.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_squares)

__all__ = ["SLUG", "score_squares", "validate"]
