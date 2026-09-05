"""Blindfold Calculation validator: enter the single move that checkmates.

MVP scope is strictly Mate in 1. The user never sees the board; they read
(or later hear) the Persian position description and submit the mating move
in SAN notation (e.g. ``Qh7#``; the trailing ``#`` is optional).

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "example": "Qe8#", "mate_count": 1}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position. The ``Puzzle.fen``
  column and ``position_json`` carry NO position data for this exercise.
- position_json: {"description_fa": "...", "side_to_move": "white"|"black",
  "mode": "mate-in-1"} (visible to frontend; the description is generated
  from the FEN by ``description.describe_position``).

Attempt model (sent by client):
    {"move": "Qh7#"}

Correctness is authoritative, never a string comparison: the submitted SAN
is parsed with ``board.parse_san`` against the stored position, and the
answer counts as CORRECT only when the move is legal AND the resulting
position is checkmate. Any legal mating move counts, so positions with
several mates accept them all.

Result rules: CORRECT or WRONG only (a single move cannot be partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "blindfold-calculation"


def mating_moves(fen: str) -> list[str]:
    """All mating moves in UCI form (used by validator + seed + tests)."""
    board = chess.Board(fen)  # raises on invalid FEN
    found: list[str] = []
    for move in board.legal_moves:
        board.push(move)
        try:
            if board.is_checkmate():
                found.append(move.uci())
        finally:
            board.pop()
    return sorted(found)


def mating_sans(fen: str) -> list[str]:
    """All mating moves in canonical SAN form (used for feedback/detail)."""
    board = chess.Board(fen)  # raises on invalid FEN
    found: list[str] = []
    for move in board.legal_moves:
        san = board.san(move)
        board.push(move)
        try:
            if board.is_checkmate():
                found.append(san)
        finally:
            board.pop()
    return sorted(found)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    fen = answer.get("fen")
    raw_move = attempt_map.get("move")

    submitted = raw_move.strip() if isinstance(raw_move, str) else ""

    def wrong(missed: list[str]) -> ValidationResult:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={
                "correct": [],
                "missed": missed,
                "wrong": [submitted] if submitted else [],
                "correct_move": missed[0] if missed else "",
            },
        )

    if not isinstance(fen, str) or not submitted:
        # Missing position or empty answer can never mate. Still reveal the
        # example so feedback stays educational (never leaks pre-submission:
        # detail is only returned for a submitted attempt).
        try:
            expected = mating_sans(fen) if isinstance(fen, str) else []
        except ValueError:
            expected = []
        example = expected[0] if expected else ""
        return wrong([example] if example else [])

    try:
        board = chess.Board(fen)
    except ValueError:
        return wrong([])

    try:
        move = board.parse_san(submitted)
    except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError, ValueError):
        try:
            expected = mating_sans(fen)
        except ValueError:
            expected = []
        return wrong([expected[0]] if expected else [])

    # parse_san only returns legal moves; push and require checkmate.
    # A fake trailing '#' never helps: only a real mate counts.
    canonical = board.san(move)
    board.push(move)
    try:
        mated = board.is_checkmate()
    finally:
        board.pop()
    if mated:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": [canonical], "missed": [], "wrong": [], "correct_move": canonical},
        )
    try:
        expected = mating_sans(fen)
    except ValueError:
        expected = []
    return wrong([expected[0]] if expected else [])
