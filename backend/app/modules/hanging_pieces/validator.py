"""Hanging Pieces validator: select every hanging piece on the board.

A piece is hanging when it is attacked by at least one opponent piece and
defended by zero friendly pieces:

    hanging(piece) = enemy_attackers > 0 AND friendly_defenders == 0

Attack relationships come from python-chess attack geometry
(`board.attackers`), NOT from legal moves: pawn pushes are not attacks,
sliding rays respect blockers, and kings attack/defend adjacent squares
even when moving there would be illegal. No exchange sequences, no engine.

Puzzle definition (stored in the puzzle row):
- FEN holds the position.
- position_json: {"fen": "...", "mode": "standard"} (visible to frontend).
- answer_json: {"squares": [...]} (never exposed; submission validation
  compares against it).

Attempt model (sent by client):
    {"selected_squares": ["e4", "h7"]}

Result rules:
- CORRECT: every hanging square selected and nothing else. When no piece
  is hanging, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when nothing is hanging).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "hanging-pieces"


def hanging_squares(fen: str) -> list[str]:
    """Compute hanging squares from a FEN (used by seed + tests).

    Inspects every occupied square (kings included, handled uniformly).
    The piece's own square is never counted as a defender. Submission
    validation compares against the stored answer and never recomputes
    from FEN or trusts client-provided square lists.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    hanging: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        if not board.attackers(not piece.color, sq):
            continue
        defenders = board.attackers(piece.color, sq) - {sq}
        if not defenders:
            hanging.append(chess.square_name(sq))
    return sorted(hanging)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # Nothing is hanging: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
