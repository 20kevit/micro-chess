"""Equal Attackers & Defenders validator.

A piece is a target when its number of enemy attackers exactly equals its
number of friendly defenders, and both numbers are greater than zero:

    target(piece) = attackers > 0 AND attackers == defenders

Counts come from python-chess attack geometry (`board.attackers`), NOT from
legal moves: pawn pushes are not attacks, sliding rays respect blockers,
and kings attack/defend adjacent squares even when moving there would be
illegal. No exchange sequences, no engine.

Puzzle definition (stored in the puzzle row):
- FEN holds the position.
- position_json: {"fen": "...", "mode": "standard"} (visible to frontend).
- answer_json: {"squares": [...]} (never exposed; submission validation
  compares against it).

Attempt model (sent by client):
    {"selected_squares": ["e4", "h7"]}

Result rules:
- CORRECT: every target square selected and nothing else. When no piece
  qualifies, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when nothing qualifies).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "equal-attackers-defenders"


def counts_for(fen: str, square: str) -> tuple[int, int]:
    """Return (attackers, defenders) for the piece on a square.

    Raises ValueError when the square is empty or the FEN is invalid.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    sq = chess.parse_square(square.strip().lower())
    piece = board.piece_at(sq)
    if piece is None:
        raise ValueError("no_piece_on_square")
    attackers = board.attackers(not piece.color, sq)
    # A piece never defends its own square; subtract defensively.
    defenders = board.attackers(piece.color, sq) - {sq}
    return len(attackers), len(defenders)


def balanced_squares(fen: str) -> list[str]:
    """Compute target squares from a FEN (used by seed + tests).

    Inspects every occupied square (kings included, handled uniformly).
    Submission validation compares against the stored answer and never
    recomputes from FEN or trusts client-provided square lists.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    targets: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        attackers = board.attackers(not piece.color, sq)
        if not attackers:
            continue
        defenders = board.attackers(piece.color, sq) - {sq}
        if len(attackers) == len(defenders):
            targets.append(chess.square_name(sq))
    return sorted(targets)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # Nothing qualifies: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
