"""Captures validator: select every enemy piece the hunter can capture.

Puzzle definition (stored in the puzzle row):
- FEN holds the position (side to move owns the hunter piece).
- position_json: {"from": "e4", "profile": "ignore-enemy-attacks"}
  (visible to frontend; the hunter square is part of the task).
- answer_json: {"squares": [...], "from": "e4", "profile": "..."}
  (never exposed; submission validation compares against it).

The answer contains only enemy-occupied squares that are capture
destinations under the puzzle's rule profile: sliding rays stop at the
first occupied square and pawn pushes are never captures. Whether the
target is defended (or the capture is tactically good) NEVER matters:
defense, exchange evaluation, and hanging-piece logic belong to other
exercises and are deliberately not consulted here.

Rule profiles are data (name -> function), not branches in the attempt
flow, mirroring Exercise 2:
- "standard": python-chess legal moves filtered to captures (king safety
  included). Used by the legacy seed puzzles.
- "ignore-enemy-attacks": pseudo-legal moves filtered to captures, so
  kings may capture defended neighbours and no king-safety puzzle is
  invented. Used by the dynamic generator.

Attempt model (sent by client):
    {"selected_squares": ["d5", "f5"]}

Result rules:
- CORRECT: every capturable square selected and nothing else. When no
  capture exists, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when no capture exists).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "captures"

STANDARD = "standard"
IGNORE_ENEMY_ATTACKS = "ignore-enemy-attacks"


def _captures_standard(board: chess.Board, origin: chess.Square) -> set[chess.Square]:
    """Normal chess legality (king safety included) for captures from one square."""
    return {m.to_square for m in board.legal_moves if m.from_square == origin and board.is_capture(m)}


def _captures_ignore_enemy_attacks(board: chess.Board, origin: chess.Square) -> set[chess.Square]:
    """Movement/blocking rules apply, but enemy-controlled squares stay capturable.

    Uses pseudo-legal moves (which ignore check), so kings may capture
    defended neighbours and the exercise never becomes a king-safety puzzle.
    Defense irrelevance falls out naturally: enemy attack maps are never
    consulted.
    """
    return {m.to_square for m in board.pseudo_legal_moves if m.from_square == origin and board.is_capture(m)}


# Rule profiles stay data (name -> function), not branches in the attempt flow,
# so future exercises can add profiles without touching core logic.
RULE_PROFILES = {
    STANDARD: _captures_standard,
    IGNORE_ENEMY_ATTACKS: _captures_ignore_enemy_attacks,
}


def capturable_squares(fen: str, hunter_square: str, profile: str = STANDARD) -> list[str]:
    """Compute capturable enemy squares for the hunter (used by seed + tests).

    Submission validation compares against the stored answer and never
    recomputes from FEN or trusts client-provided destination lists.
    """
    fn = RULE_PROFILES.get(profile)
    if fn is None:
        raise ValueError(f"unknown_rule_profile:{profile}")
    board = chess.Board(fen)  # raises on invalid FEN
    origin = chess.parse_square(hunter_square.strip().lower())
    if board.piece_at(origin) is None:
        raise ValueError("no_piece_on_hunter_square")
    return sorted(chess.square_name(sq) for sq in fn(board, origin))


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # No capture exists: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
