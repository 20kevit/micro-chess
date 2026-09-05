"""Undefended Pieces validator: select every undefended non-king piece.

A non-king piece is undefended iff:

    at least one valid enemy piece attacks it
    AND
    no valid friendly piece defends it

Validity is chess attack geometry (``board.attackers``: pawn diagonals,
knight jumps, sliding rays with blockers, kings adjacent) MINUS absolutely
pinned pieces:

- An absolutely pinned piece (``board.is_pinned``: moving it would expose
  its own King to check) does NOT count as an attacker or defender.
- A piece pinned to a Queen or any other non-King piece is NOT absolutely
  pinned and still counts normally.
- The King itself is never an answer, but it still attacks/defends adjacent
  squares for other pieces' evaluation.

Puzzle definition (stored in the puzzle row):
- FEN holds the position.
- position_json: {"fen": "...", "mode": "standard"} (visible to frontend).
- answer_json: {"squares": [...]} (never exposed; submission validation
  compares against it).

Attempt model (sent by client):
    {"selected_squares": ["a1", "f6"]}

Result rules:
- CORRECT: every undefended square selected and nothing else. When nothing
  is undefended, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when nothing is undefended).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "undefended-pieces"


def _valid_attackers(board: chess.Board, color: chess.Color, square: chess.Square) -> set[chess.Square]:
    """Enemy squares attacking ``square``, excluding absolutely pinned pieces."""
    return {sq for sq in board.attackers(color, square) if not board.is_pinned(color, sq)}


def undefended_squares(fen: str) -> list[str]:
    """Compute undefended non-king squares from a FEN (used by seed + tests).

    Inspects every occupied square except kings. The piece's own square is
    never counted as a defender. Submission validation compares against the
    stored answer and never recomputes from FEN or trusts client input.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    undefended: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        if piece.piece_type == chess.KING:
            continue
        attackers = _valid_attackers(board, not piece.color, sq)
        if not attackers:
            continue
        defenders = _valid_attackers(board, piece.color, sq) - {sq}
        if not defenders:
            undefended.append(chess.square_name(sq))
    return sorted(undefended)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # Nothing is undefended: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
