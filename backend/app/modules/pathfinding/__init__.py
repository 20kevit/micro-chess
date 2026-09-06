"""Pathfinding exercise (simple version): one white piece to the star."""

from app.modules.exercises import registry
from app.modules.pathfinding.scoring import score_path
from app.modules.pathfinding.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_path)

__all__ = ["SLUG", "validate", "score_path"]
