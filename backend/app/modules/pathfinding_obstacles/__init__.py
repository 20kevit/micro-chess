"""Exercise 7: Pathfinding with Obstacles (one white piece to the star,
around/through black enemies with destination-safety and capture rules)."""

from app.modules.exercises import registry
from app.modules.pathfinding_obstacles.scoring import score_obstacle_path
from app.modules.pathfinding_obstacles.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_obstacle_path)

__all__ = ["SLUG", "validate", "score_obstacle_path"]
