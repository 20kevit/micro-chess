"""Legal Destinations validator: select all legal destination squares.

Puzzle definition (stored in the puzzle row):
- FEN holds the position (side to move owns the target piece).
- position_json: {"from": "d4", "profile": "standard"} (visible to frontend;
  the target square is part of the task).
- answer_json: {"squares": [...], "from": "d4", "profile": "standard"}
  (never exposed; submission validation compares against it).

Attempt model (sent by client):
    {"selected_squares": ["e6", "f5"]}

Result rules (same as Piece Recognition):
- CORRECT: every required square selected, no incorrect selections.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes empty and malformed-only answers).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, split_squares

SLUG = "legal-destinations"

STANDARD = "standard"
IGNORE_ENEMY_ATTACKS = "ignore-enemy-attacks"


def _destinations_standard(board: chess.Board, from_square: chess.Square) -> set[chess.Square]:
    """Normal chess legality (king safety included) for moves from one square."""
    return {m.to_square for m in board.legal_moves if m.from_square == from_square}


def _destinations_ignore_enemy_attacks(board: chess.Board, from_square: chess.Square) -> set[chess.Square]:
    """Movement/blocking rules apply, but enemy-controlled squares stay legal.

    Uses pseudo-legal moves (which ignore check), so kings may step into
    attack and pinned pieces move freely. Custom-rule variants plug in here.
    """
    return {m.to_square for m in board.pseudo_legal_moves if m.from_square == from_square}


# Rule profiles stay data (name -> function), not branches in the attempt flow,
# so future exercises can add profiles without touching core logic.
RULE_PROFILES = {
    STANDARD: _destinations_standard,
    IGNORE_ENEMY_ATTACKS: _destinations_ignore_enemy_attacks,
}


def legal_destinations(fen: str, from_square: str, profile: str = STANDARD) -> list[str]:
    """Compute destination squares for a target piece (used by seed + tests).

    Submission validation compares against the stored answer and never
    recomputes from FEN or trusts client-provided destination lists.
    """
    fn = RULE_PROFILES.get(profile)
    if fn is None:
        raise ValueError(f"unknown_rule_profile:{profile}")
    board = chess.Board(fen)  # raises on invalid FEN
    origin = chess.parse_square(from_square.strip().lower())
    if board.piece_at(origin) is None:
        raise ValueError("no_piece_on_target_square")
    return sorted(chess.square_name(sq) for sq in fn(board, origin))


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    # Exact set match (same contract as Piece Recognition): empty==empty is
    # CORRECT so zero-target questions terminate correctly in practice.
    expected, _ = split_squares(puzzle_answer.get("squares", []))
    selected, malformed = split_squares(attempt.get("selected_squares", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
