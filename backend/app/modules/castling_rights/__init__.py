"""Castling Rights exercise: select every currently legal castling option."""

from app.modules.exercises import registry
from app.modules.castling_rights.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
