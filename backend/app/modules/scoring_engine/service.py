"""Scoring: maps attempt results to points. Pure functions, no DB."""

from app.modules.rule_engine.base import AttemptResult


def score_for(result: AttemptResult) -> float:
    if result == AttemptResult.CORRECT:
        return 1.0
    if result == AttemptResult.PARTIAL:
        return 0.5
    return 0.0
