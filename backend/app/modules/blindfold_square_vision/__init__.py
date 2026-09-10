"""Blindfold Square Vision exercise: what color is the square?"""

from app.modules.blindfold_square_vision.scoring import score_square_vision
from app.modules.blindfold_square_vision.validator import SLUG, validate
from app.modules.exercises import registry

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_square_vision)

__all__ = ["SLUG", "validate"]
