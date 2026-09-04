"""Material Comparison validator: which side is heavier?

This exercise is purely about material value: no python-chess, no board,
no kings. Piece color is irrelevant. Only piece type and its configured
value matter:

    Pawn = 1, Knight = 3, Bishop = 3, Rook = 5, Queen = 9.

Puzzle definition (stored in the puzzle row, never fully exposed):
- answer_json: {"left": [...], "right": [...]} (server-side source of truth).
- position_json: {"left": [...], "right": [...]} (visible; both sides are
  displayed, never the verdict).

Attempt model (sent by client):
    {"choice": "left"}  (or "right" / "equal")

A submission is CORRECT when the choice matches the relation derived from
the stored totals. Client-supplied totals are ignored; the backend always
recalculates both sides itself.

Result rules: CORRECT or WRONG only. Malformed input fails safely as WRONG
and never crashes the API.
"""

from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "heavier-side"

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}

CHOICES = ("left", "right", "equal")


def normalize_piece(raw: Any) -> str | None:
    """Uppercase/validate a single piece id. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    piece = raw.strip().upper()
    return piece if piece in VALUES else None


def total_value(pieces: list[str]) -> int:
    """Total material value. Caller must pass normalized pieces only."""
    return sum(VALUES[p] for p in pieces)


def normalize_choice(raw: Any) -> str | None:
    """Lowercase/validate the submitted choice. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    choice = raw.strip().lower()
    return choice if choice in CHOICES else None


def expected_choice(left_value: int, right_value: int) -> str:
    """Relation derived from the two totals. No client input involved."""
    if left_value > right_value:
        return "left"
    if right_value > left_value:
        return "right"
    return "equal"


def clean_list(raw: Any) -> list[str] | None:
    """Normalize a piece list, or None when any entry is malformed."""
    if not isinstance(raw, list):
        return None
    cleaned: list[str] = []
    for entry in raw:
        piece = normalize_piece(entry)
        if piece is None:
            return None
        cleaned.append(piece)
    return cleaned


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    left = clean_list(puzzle_answer.get("left") if isinstance(puzzle_answer, dict) else None)
    right = clean_list(puzzle_answer.get("right") if isinstance(puzzle_answer, dict) else None)
    choice = normalize_choice(attempt.get("choice") if isinstance(attempt, dict) else None)

    detail: dict[str, Any] = {"correct": [], "missed": [], "wrong": []}
    if left is None or right is None or choice is None:
        if choice is not None:
            detail["wrong"] = [choice]
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)

    left_value = total_value(left)
    right_value = total_value(right)
    detail["left_value"] = left_value
    detail["right_value"] = right_value
    if choice == expected_choice(left_value, right_value):
        detail["correct"] = [choice]
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    detail["wrong"] = [choice]
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
