"""Pathfinding scoring (Exercise 6): optimal moves, extra moves, illegal tries.

score = optimal_moves * 5 - max(0, actual_moves - optimal_moves) * 2
        - illegal_attempts * 3

- ``optimal_moves`` is the server-computed BFS minimum (never trusted
  from the client); ``actual_moves`` = len(path) - 1 from the validated
  path; ``illegal_attempts`` = the client's illegal-try counter,
  clamped to >= 0 server-side.
- Legal moves inside the optimal count are never penalized; each extra
  legal move costs exactly -2 once; each illegal attempt costs -3.
- Scores may be negative; nothing clamps them here (project-wide policy
  keeps negatives, same as Exercises 1-5). The result label
  (CORRECT/WRONG) is computed independently by the validator.
"""

from __future__ import annotations

from typing import Any

from app.modules.rule_engine.base import ValidationResult

OPTIMAL_POINTS = 5
EXTRA_MOVE_COST = 2
ILLEGAL_ATTEMPT_COST = 3


def _count_moves(detail: dict[str, Any]) -> tuple[int, int, int]:
    moves = detail.get("moves")
    optimal = detail.get("optimal_moves")
    illegal = detail.get("illegal_attempts")
    moves_n = moves if isinstance(moves, int) and moves >= 0 else 0
    optimal_n = optimal if isinstance(optimal, int) and optimal >= 0 else 0
    illegal_n = illegal if isinstance(illegal, int) and illegal >= 0 else 0
    return moves_n, optimal_n, illegal_n


def score_path(validation: ValidationResult) -> float:
    detail = validation.detail if isinstance(validation.detail, dict) else {}
    moves, optimal, illegal = _count_moves(detail)
    extra = max(0, moves - optimal)
    return float(optimal * OPTIMAL_POINTS - extra * EXTRA_MOVE_COST - illegal * ILLEGAL_ATTEMPT_COST)
