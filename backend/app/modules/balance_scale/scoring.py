"""Balance Scale scoring (Exercise 10): minimum piece count wins.

score = max(0, 10 - extra_pieces)
where extra_pieces = used_piece_count - optimal_count.

- Solving with the minimum possible number of pieces scores 10.
- Every extra piece costs exactly 1 point; the floor is 0 (never negative).
- Non-exact attempts (WRONG) score 0: the user may experiment freely —
  adding/removing pieces before balance is never penalized.
- ``optimal_count``/``used_count`` come from the validator's server-side
  detail (recomputed from the stored puzzle); client-supplied numbers are
  ignored. Any exact combination is accepted; only the count matters.
"""

from __future__ import annotations

from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult


def _as_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def score_balance(validation: ValidationResult) -> float:
    if validation.result != AttemptResult.CORRECT:
        return 0.0
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    used = _as_count(detail.get("used_count"))
    optimal = _as_count(detail.get("optimal_count"))
    if used is None or optimal is None:
        return 0.0
    return float(max(0, 10 - (used - optimal)))
