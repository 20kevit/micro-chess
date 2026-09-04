"""Equal Attackers & Defenders exercise: find equally attacked and defended pieces."""

from app.modules.exercises import registry
from app.modules.equal_attackers_defenders.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
