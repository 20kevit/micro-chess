"""Get Out of Check scoring: per-move, server-authoritative.

score = (correct_selected x +5) - (missed_targets x 2) - (wrong_selected x 3)

- Counts come from the validation detail (backend-computed, never trusted
  from the client). Malformed arrows arrive inside ``detail["wrong"]``
  and cost -3 each, like any other wrong arrow.
- Unlike Giving Check there is no zero-target bonus: a valid puzzle
  always has at least one escape (positions with zero escapes are
  checkmate and never generated), so an empty submission simply misses
  everything.
- Scores may be negative; nothing clamps them here. The result label
  (CORRECT/PARTIAL/WRONG) is computed independently by the validator.
"""

from app.modules.rule_engine.base import ValidationResult

CORRECT_POINTS = 5
MISSED_COST = 2
WRONG_COST = 3


def _count(value: object) -> int:
    return len(value) if isinstance(value, (list, tuple, set)) else 0


def score_moves(validation: ValidationResult) -> float:
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    correct = _count(detail.get("correct"))
    missed = _count(detail.get("missed"))
    wrong = _count(detail.get("wrong"))
    return float(correct * CORRECT_POINTS - missed * MISSED_COST - wrong * WRONG_COST)
