"""Captures validator: select every enemy piece the hunter can legally capture.

Puzzle definition (stored in the puzzle row):
- FEN holds the position (side to move owns the hunter piece).
- position_json: {"from": "e4"} (visible to frontend; the hunter square
  is part of the task).
- answer_json: {"squares": [...], "from": "e4"} (never exposed; submission
  validation compares against it).

The answer contains only enemy-occupied squares that are legal capture
destinations: sliding rays stop at the first occupied square, pawn pushes
are never captures, and king captures respect king safety. All of this
follows from python-chess legal move generation filtered to captures.

Attempt model (sent by client):
    {"selected_squares": ["d5", "f5"]}

Result rules:
- CORRECT: every capturable square selected and nothing else. When no
  capture exists, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when no capture exists).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "captures"


def capturable_squares(fen: str, hunter_square: str) -> list[str]:
    """Compute capturable enemy squares for the hunter (used by seed + tests).

    Submission validation compares against the stored answer and never
    recomputes from FEN or trusts client-provided destination lists.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    origin = chess.parse_square(hunter_square.strip().lower())
    if board.piece_at(origin) is None:
        raise ValueError("no_piece_on_hunter_square")
    return sorted(
        chess.square_name(m.to_square)
        for m in board.legal_moves
        if m.from_square == origin and board.is_capture(m)
    )


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # No capture exists: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
