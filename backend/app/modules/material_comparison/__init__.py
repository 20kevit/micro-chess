"""Heavier Side exercise: which side is ahead on material only?"""

from app.modules.exercises import registry
from app.modules.material_comparison.scoring import score_heavier_side
from app.modules.material_comparison.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_heavier_side)

__all__ = ["SLUG", "validate"]
