"""Checkmate validator: classify the side-to-move check state.

The answer is derived from the stored FEN with python-chess as the
authoritative source of truth:

- checkmate: side to move is in check AND has no legal moves.
- check: side to move is in check BUT has at least one legal move.
- not_check: side to move is not in check (stalemate included).

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "..."}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position — never from a stored
  classification.

Attempt model (sent by client):
    {"choice": "checkmate"}  (or "check" / "not_check")

A submission is CORRECT when the choice matches the derived state.
Client-supplied flags never influence validation.

Result rules: CORRECT or WRONG only. Malformed input fails safely as WRONG
and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "is-checkmate"

CHOICES = ("checkmate", "check", "not_check")


def classify(fen: str) -> str:
    """Derive the check state from a FEN with python-chess.

    Raises ValueError on invalid FEN or on positions unusable for this
    exercise (a missing king).
    """
    board = chess.Board(fen)  # raises on invalid FEN
    if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
        raise ValueError("position needs both kings")
    if board.is_checkmate():
        return "checkmate"
    if board.is_check():
        return "check"
    return "not_check"


def normalize_choice(raw: Any) -> str | None:
    """Lowercase/validate a submitted choice. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    choice = raw.strip().lower()
    return choice if choice in CHOICES else None


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    choice = normalize_choice(attempt.get("choice") if isinstance(attempt, dict) else None)

    detail: dict[str, Any] = {"correct": [], "missed": [], "wrong": []}
    if not isinstance(fen, str) or choice is None:
        if choice is not None:
            detail["wrong"] = [choice]
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    try:
        expected = classify(fen)
    except ValueError:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if choice == expected:
        detail["correct"] = [choice]
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    detail["wrong"] = [choice]
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
