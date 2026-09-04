"""Legal Destinations exercise: select all legal destinations of a target piece."""

from app.modules.exercises import registry
from app.modules.legal_destinations.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
