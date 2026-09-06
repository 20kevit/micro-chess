"""Heavier Side validator: which side is ahead on MATERIAL only.

New spec (real board positions from the shared ``puzzles.db``):

- answer_json: {"fen": "..."} (server-only source of truth).
- position_json: {"fen": "...", "mode": "standard"} (visible board).
- Attempt: {"choice": "white"} (or "black" / "equal").

The expected choice is recomputed from the stored FEN with the isolated
``material`` calculator (Pawn=1, N=3, B=3, R=5, Q=9, K=0). No engine,
no themes, no ratings, no moves, no positional evaluation. Client
totals/scores are ignored.

Legacy rows (left/right piece-list shape from the earlier scale-pan
prototype) are still graded by their original rule so existing databases
keep working; all newly generated puzzles use the FEN shape.

Result rules: CORRECT or WRONG only. Malformed input fails safely as
WRONG and never crashes the API.
"""

from typing import Any

from app.modules.material_comparison import material as mat
from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "heavier-side"

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}

CHOICES = ("white", "black", "equal")

# Legacy scale-pan choices (kept for old rows only).
LEGACY_CHOICES = ("left", "right", "equal")


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


def normalize_legacy_choice(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    choice = raw.strip().lower()
    return choice if choice in LEGACY_CHOICES else None


def expected_choice(white_value: int, black_value: int) -> str:
    """Relation derived from the two totals. No client input involved."""
    return mat.classify(white_value, black_value)


def expected_choice_legacy(left_value: int, right_value: int) -> str:
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


def _validate_legacy(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    left = clean_list(puzzle_answer.get("left"))
    right = clean_list(puzzle_answer.get("right"))
    choice = normalize_legacy_choice(attempt.get("choice") if isinstance(attempt, dict) else None)

    detail: dict[str, Any] = {"correct": [], "missed": [], "wrong": []}
    if left is None or right is None or choice is None:
        if choice is not None:
            detail["wrong"] = [choice]
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)

    left_value = total_value(left)
    right_value = total_value(right)
    detail["left_value"] = left_value
    detail["right_value"] = right_value
    if choice == expected_choice_legacy(left_value, right_value):
        detail["correct"] = [choice]
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    detail["wrong"] = [choice]
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    # Legacy rows have no "fen" key; grade them by the original rule.
    if "fen" not in answer and ("left" in answer or "right" in answer):
        return _validate_legacy(answer, attempt)

    fen = answer.get("fen")
    choice = normalize_choice(attempt.get("choice") if isinstance(attempt, dict) else None)

    detail: dict[str, Any] = {"correct": [], "missed": [], "wrong": []}
    if not isinstance(fen, str) or choice is None:
        if choice is not None:
            detail["wrong"] = [choice]
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    try:
        white_value, black_value = mat.material_from_fen(fen)
        expected = mat.classify(white_value, black_value)
    except ValueError:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    detail["white_material"] = white_value
    detail["black_material"] = black_value
    detail["expected"] = expected
    if choice == expected:
        detail["correct"] = [choice]
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    detail["wrong"] = [choice]
    detail["missed"] = [expected]
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
