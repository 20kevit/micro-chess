"""Chinese Board exercise: memorize a real position, rebuild it exactly."""

from app.modules.exercises import registry
from app.modules.chinese_board.scoring import score_chinese_board
from app.modules.chinese_board.validator import SLUG, validate

registry.register_validator(SLUG, validate)
registry.register_scorer(SLUG, score_chinese_board)

__all__ = ["SLUG", "validate"]
