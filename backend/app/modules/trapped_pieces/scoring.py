"""Trapped Pieces scoring: per-square, server-authoritative.

score = (correct_selected x +5) - (missed_targets x 2) - (wrong_selected x 2)

with one explicit exception: a correctly answered zero-target question
(empty target set, empty selection) awards a +5 completion bonus instead
of 0, so finding "nothing there" still feels rewarding. Generated
puzzles always contain at least one trapped piece (empties are
discarded), so the bonus only triggers on legacy/hand-made rows.

- Counts come from the validation detail (backend-computed, never trusted
  from the client). Malformed selections arrive inside ``detail["wrong"]``
  and cost -2 each, like any other wrong square.
- The zero-target bonus applies ONLY when the validation result is CORRECT
  and all three detail lists are empty — that signature uniquely means
  "empty target, empty selection".
- Scores may be negative; nothing clamps them here. The result label
  (CORRECT/PARTIAL/WRONG) is computed independently by the validator.
- Speed mode reuses this exact scorer with single-answer positions: a
  correct tap scores +5; a wrong tap scores -4 (-2 wrong plus -2 for the
  missed trapped piece), because a Speed position always holds exactly
  one trapped piece.
"""

from app.modules.rule_engine.base import AttemptResult, ValidationResult

CORRECT_POINTS = 5
MISSED_COST = 2
WRONG_COST = 2
# Completion bonus for a correctly answered zero-target question.
ZERO_TARGET_BONUS = 5


def _count(value: object) -> int:
    return len(value) if isinstance(value, (list, tuple, set)) else 0


def score_squares(validation: ValidationResult) -> float:
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    correct = _count(detail.get("correct"))
    missed = _count(detail.get("missed"))
    wrong = _count(detail.get("wrong"))
    if (
        validation.result == AttemptResult.CORRECT
        and correct == 0
        and missed == 0
        and wrong == 0
    ):
        return float(ZERO_TARGET_BONUS)
    return float(correct * CORRECT_POINTS - missed * MISSED_COST - wrong * WRONG_COST)
