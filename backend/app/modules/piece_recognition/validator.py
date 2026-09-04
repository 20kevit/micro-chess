"""Piece Recognition validator: which squares hold the target pieces?

Answer model (stored in puzzle.answer_json):
    {"squares": ["a2", "c4"]}

Attempt model (sent by client):
    {"selected_squares": ["a2", "e5"]}

Result rules:
- CORRECT: every required square selected, no incorrect selections.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes empty and malformed-only answers).

Malformed square names are treated as incorrect selections, never as crashes.
New target definitions only need a color + piece-kind set (see TARGETS and
squares_for_target); the validation flow itself never changes.
"""

from typing import Any

from app.modules.chess_engine import board as chess_board
from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "piece-recognition"

# Piece kinds use python-chess symbols (lowercase). "minor" = bishops + knights.
# A target is {"color": "white" | "black" | "any", "kinds": [...]}.
# Kept as data (not separate exercise types) so new targets plug in freely.
TARGETS: dict[str, dict[str, Any]] = {
    "white-pawn": {"color": "white", "kinds": ["p"]},
    "black-pawn": {"color": "black", "kinds": ["p"]},
    "white-knight": {"color": "white", "kinds": ["n"]},
    "black-knight": {"color": "black", "kinds": ["n"]},
    "white-bishop": {"color": "white", "kinds": ["b"]},
    "black-bishop": {"color": "black", "kinds": ["b"]},
    "white-rook": {"color": "white", "kinds": ["r"]},
    "black-rook": {"color": "black", "kinds": ["r"]},
    "white-queen": {"color": "white", "kinds": ["q"]},
    "black-queen": {"color": "black", "kinds": ["q"]},
    "queen-any": {"color": "any", "kinds": ["q"]},
    "minor-white": {"color": "white", "kinds": ["b", "n"]},
    "minor-black": {"color": "black", "kinds": ["b", "n"]},
}

_FILES = "abcdefgh"


def squares_for_target(fen: str, target: dict[str, Any]) -> list[str]:
    """Compute answer squares for a target from a FEN (used by seed + tests).

    Display/seed helper only; submission validation compares against the
    stored answer and never recomputes from FEN.
    """
    color = target.get("color", "any")
    kinds = set(target.get("kinds", []))
    found: list[str] = []
    for file_ in _FILES:
        for rank in "12345678":
            sq = f"{file_}{rank}"
            symbol = chess_board.piece_at(fen, sq)
            if symbol is None or symbol.lower() not in kinds:
                continue
            is_white = symbol.isupper()
            if color == "white" and not is_white:
                continue
            if color == "black" and is_white:
                continue
            found.append(sq)
    return sorted(found)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
