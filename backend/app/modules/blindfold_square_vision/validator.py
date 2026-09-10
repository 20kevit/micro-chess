"""Blindfold Square Vision validator: what color is the square?

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"square": "d5"} (server-only source of truth).
- position_json: {"square": "d5", "mode": "standard"} (the square IS the
  question, so it is public; only the COLOR is secret).
- fen: the empty-board FEN (practice renders an empty tappable board).

Square colors are NEVER stored: they are derived deterministically from
the coordinate with the standard convention (a1 is dark; adjacent
squares alternate). "white" = light square, "black" = dark square.

Attempt models (sent by clients):
- Practice (visible board): {"square": "<clicked>"}.
- Speed (no board): {"choice": "white"} (or "black").

A submission is CORRECT when the clicked square is the target (practice)
or the choice matches the derived color (speed). Client-supplied colors
never influence validation.

Result rules: CORRECT or WRONG only. Malformed input fails safely as
WRONG and never crashes the API.
"""

from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "blindfold-square-vision"

CHOICES = ("white", "black")


def square_color(square: str) -> str:
    """Deterministic square color: "white" (light) or "black" (dark).

    Standard convention: a1 is dark and adjacent squares alternate, so a
    square is light exactly when (file + rank) is odd with 0-based
    indices. Caller must pass a normalized square name.
    """
    file = ord(square[0]) - ord("a")
    rank = int(square[1]) - 1
    return "white" if (file + rank) % 2 == 1 else "black"


def normalize_choice(raw: Any) -> str | None:
    """Lowercase/validate a submitted color choice. None when malformed."""
    if not isinstance(raw, str):
        return None
    choice = raw.strip().lower()
    return choice if choice in CHOICES else None


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    target = normalize_square(answer.get("square"))
    if target is None:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": []},
        )

    if not isinstance(attempt, dict):
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": []},
        )

    clicked = normalize_square(attempt.get("square"))
    if clicked is not None:
        # Practice: the user taps a square on the visible board.
        if clicked == target:
            return ValidationResult(
                result=AttemptResult.CORRECT,
                message_key="feedback.correct",
                detail={"correct": [target], "missed": [], "wrong": []},
            )
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [target], "wrong": [clicked]},
        )

    choice = normalize_choice(attempt.get("choice"))
    if choice is not None:
        # Speed: the user picks white/black with no board shown.
        expected = square_color(target)
        if choice == expected:
            return ValidationResult(
                result=AttemptResult.CORRECT,
                message_key="feedback.correct",
                detail={"correct": [choice], "missed": [], "wrong": []},
            )
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [expected], "wrong": [choice]},
        )

    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={"correct": [], "missed": [], "wrong": []},
    )
