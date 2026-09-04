"""Feedback: maps results to i18n message keys. No rating/scoring math here."""

from app.modules.rule_engine.base import AttemptResult

_KEYS: dict[AttemptResult, str] = {
    AttemptResult.CORRECT: "feedback.correct",
    AttemptResult.PARTIAL: "feedback.partial",
    AttemptResult.WRONG: "feedback.wrong",
    AttemptResult.TIMEOUT: "feedback.timeout",
    AttemptResult.SKIPPED: "feedback.skipped",
    AttemptResult.ABANDONED: "feedback.abandoned",
}


def feedback_key_for(result: AttemptResult) -> str:
    return _KEYS[result]
