"""Scoring is a pure result -> points mapping."""

from app.modules.rule_engine.base import AttemptResult
from app.modules.scoring_engine.service import score_for


def test_scores():
    assert score_for(AttemptResult.CORRECT) == 1.0
    assert score_for(AttemptResult.PARTIAL) == 0.5
    assert score_for(AttemptResult.WRONG) == 0.0
    assert score_for(AttemptResult.TIMEOUT) == 0.0
    assert score_for(AttemptResult.SKIPPED) == 0.0
    assert score_for(AttemptResult.ABANDONED) == 0.0
