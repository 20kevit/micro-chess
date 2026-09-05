"""Piece Recognition scoring: per-square, server-authoritative.

score = (correct_selected x +5) - (missed_targets x 1) - (wrong_selected x 2)

- Counts come from the validation detail (backend-computed, never trusted
  from the client). Malformed selections arrive inside ``detail["wrong"]``
  and cost -2 each, like any other wrong square.
- A correctly answered zero-target question scores 0: no +5 is awarded
  merely for matching the empty set.
- Scores may be negative (e.g. -4); nothing clamps them here. The result
  label (CORRECT/PARTIAL/WRONG) is computed independently by the validator.
"""

from app.modules.rule_engine.base import ValidationResult

CORRECT_POINTS = 5
MISSED_COST = 1
WRONG_COST = 2


def _count(value: object) -> int:
    return len(value) if isinstance(value, (list, tuple, set)) else 0


def score_squares(validation: ValidationResult) -> float:
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    correct = _count(detail.get("correct"))
    missed = _count(detail.get("missed"))
    wrong = _count(detail.get("wrong"))
    return float(correct * CORRECT_POINTS - missed * MISSED_COST - wrong * WRONG_COST)
