"""Trapped Pieces validator: select every trapped non-king piece.

A non-king piece is trapped when it has zero pseudo-legal moves:

    trapped(piece) = pseudo_legal_moves(piece) == 0

Pseudo-legal (not legal) is deliberate: a pinned piece still has
pseudo-legal moves along/around the pin, so it is NOT trapped even when
it has zero legal moves. Kings are never trapped. Pawn pushes, double
pushes, captures, and promotions all count as moves; captures count.

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

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "trapped-pieces"


def trapped_squares(fen: str) -> list[str]:
    """Compute trapped squares from a FEN (used by seed + tests).

    Inspects every non-king piece on both sides. The side to move in the
    FEN is ignored: board.turn is set to each piece's own color before
    generating its pseudo-legal moves. Submission validation compares
    against the stored answer and never recomputes from FEN or trusts
    client-provided square lists.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    trapped: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        board.turn = piece.color
        mask = chess.BB_SQUARES[sq]
        if not any(True for _ in board.generate_pseudo_legal_moves(from_mask=mask)):
            trapped.append(chess.square_name(sq))
    return sorted(trapped)


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
