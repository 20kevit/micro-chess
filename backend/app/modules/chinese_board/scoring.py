"""Chinese Board scoring: per-piece, server-authoritative.

score = 5 * correct - 2 * (wrong + missed)

- Counts come from the validation detail (backend-computed, never trusted
  from the client). ``detail["wrong"]`` already contains BOTH wrong-square
  pairs and extra pieces (every user-side error exactly once);
  ``detail["missed"]`` contains every original-side gap (missing pieces;
  wrong-square originals are reported via ``missed_squares`` for the board
  overlay but count their single error on the user side). The two lists
  are disjoint by construction, so a queen remembered on the wrong square
  is ONE error (-2), never a missing plus an extra.
- Scores may be negative; nothing clamps them here (no floor — a board
  full of guesses can legitimately score below zero).
- The result label (CORRECT/WRONG) is computed independently by the
  validator; this module only maps the piece counts to points.
"""

from app.modules.rule_engine.base import ValidationResult

CORRECT_POINTS = 5.0
ERROR_COST = -2.0


def _count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def score_chinese_board(validation: ValidationResult) -> float:
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    n_correct = _count(detail.get("correct", []))
    n_errors = _count(detail.get("wrong", [])) + _count(
        detail.get("missed", detail.get("missing", []))
    )
    return float(n_correct * CORRECT_POINTS + n_errors * ERROR_COST)
