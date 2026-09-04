"""Pathfinding exercise: walk the selected piece safely to the star square."""

from app.modules.exercises import registry
from app.modules.pathfinding.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
