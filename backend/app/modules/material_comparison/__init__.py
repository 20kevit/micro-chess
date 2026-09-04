"""Material Comparison exercise: which side is heavier?"""

from app.modules.exercises import registry
from app.modules.material_comparison.validator import SLUG, validate

registry.register_validator(SLUG, validate)

__all__ = ["SLUG", "validate"]
