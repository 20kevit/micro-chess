"""Opening Move Reconstruction exercise: rebuild the opening from move one."""

from app.modules.exercises import registry
from app.modules.opening_move_reconstruction.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
