"""Trapped Pieces validator: select every trapped piece square.

A piece is trapped when it has zero SAFE destinations (see
``detector.py``: legal moves filtered by Static Exchange Evaluation, so
a defended destination with a favorable recapture still counts as an
escape). Candidates are Kings, Queens, Rooks, Bishops and Knights of
either color; pawns are never trapped.

Puzzle definition (stored in the puzzle row):
- FEN holds the position.
- position_json: {"fen": "...", "mode": "standard"} (visible to frontend).
- answer_json: {"squares": [...]} (never exposed; submission validation
  compares against it).

Attempt model (sent by client):
    {"selected_squares": ["a1", "c8"]}

Result rules:
- CORRECT: every trapped square selected and nothing else. When no piece
  is trapped, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when nothing is trapped).
"""

from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares
from app.modules.trapped_pieces.detector import trapped_squares

SLUG = "trapped-pieces"

__all__ = ["SLUG", "trapped_squares", "validate"]


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # Nothing is trapped: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
