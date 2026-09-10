"""Blindfold Square Vision scoring: fast binary answers, server-authoritative.

score = +5 when CORRECT, -3 when WRONG.

- Counts come from the validation result (backend-computed, never trusted
  from the client). Scores may be negative; nothing clamps them here.
- The result label (CORRECT/WRONG) is computed independently by the
  validator; this module only maps it to points.
"""

from app.modules.rule_engine.base import AttemptResult, ValidationResult

CORRECT_POINTS = 5.0
WRONG_COST = -3.0


def score_square_vision(validation: ValidationResult) -> float:
    if validation.result == AttemptResult.CORRECT:
        return float(CORRECT_POINTS)
    return float(WRONG_COST)
