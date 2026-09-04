"""Balance Scale validator: match the right pan's material value.

This exercise is intentionally independent of chess rules: no python-chess,
no board, no kings. Only piece type and its configured value matter; color
is irrelevant.

Puzzle definition (stored in the puzzle row, never fully exposed):
- answer_json: {"bank": [...], "right": [...]} (server-side source of truth).
- position_json: {"bank": [...], "right": [...]} (visible; the bank and the
  right pan are displayed, never the solution).

Attempt model (sent by client):
    {"pieces": ["R", "R", "B", "P"]}

A submission is CORRECT when every submitted piece exists in the bank
(counting duplicates), and the submitted total equals the right-pan total.
Any valid combination with the right total counts; the validator never
compares against one hardcoded answer.

Result rules: CORRECT or WRONG only. Malformed input fails safely as WRONG
and never crashes the API.
"""

from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "balance-scale"

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}


def normalize_piece(raw: Any) -> str | None:
    """Uppercase/validate a single piece id. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    piece = raw.strip().upper()
    return piece if piece in VALUES else None


def split_pieces(raw: Any) -> tuple[list[str], list[str]]:
    """Split raw input into (valid pieces, malformed entries).

    Malformed entries are returned as strings so callers can fail safely
    without crashing.
    """
    items = raw if isinstance(raw, list) else []
    valid: list[str] = []
    malformed: list[str] = []
    for entry in items:
        piece = normalize_piece(entry)
        if piece is None:
            malformed.append(str(entry))
        else:
            valid.append(piece)
    return valid, malformed


def total_value(pieces: list[str]) -> int:
    """Total material value. Caller must pass normalized pieces only."""
    return sum(VALUES[p] for p in pieces)


def counts(pieces: list[str]) -> dict[str, int]:
    """Multiset counts, so duplicate pieces are handled correctly."""
    result: dict[str, int] = {}
    for piece in pieces:
        result[piece] = result.get(piece, 0) + 1
    return result


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    bank, bank_bad = split_pieces(puzzle_answer.get("bank") if isinstance(puzzle_answer, dict) else None)
    right, right_bad = split_pieces(puzzle_answer.get("right") if isinstance(puzzle_answer, dict) else None)
    submitted, malformed = split_pieces(attempt.get("pieces") if isinstance(attempt, dict) else None)

    target_value = total_value(right)
    submitted_value = total_value(submitted)
    detail: dict[str, Any] = {
        "correct": [],
        "missed": [],
        "wrong": submitted + malformed,
        "submitted_value": submitted_value,
        "target_value": target_value,
    }
    if bank_bad or right_bad or malformed:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    available = counts(bank)
    for piece, needed in counts(submitted).items():
        if available.get(piece, 0) < needed:
            return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if submitted_value == target_value:
        detail["correct"] = submitted
        detail["wrong"] = []
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
