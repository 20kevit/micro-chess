"""Trapped Pieces exercise: select every trapped non-king piece."""

from app.modules.exercises import registry
from app.modules.trapped_pieces.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
