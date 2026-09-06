"""Balance Scale exercise (Exercise 10, ترازو): match the left pan's value."""

from app.modules.exercises import registry
from app.modules.balance_scale.scoring import score_balance
from app.modules.balance_scale.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_balance)

__all__ = ["SLUG", "validate", "score_balance"]
