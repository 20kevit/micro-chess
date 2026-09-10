"""Blindfold Calculation validator: find the best move without seeing the board.

The user reads the structured Persian position description and submits
the best move in SAN notation (e.g. ``Nf3``; ``+``/``#`` suffixes are
accepted because SAN identity is the move, not the string).

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "solution": "e2e4", "puzzle_id": "...",
  "rating": 1500}. The FEN comes from the shared ``puzzles.db`` and the
  solution is the FIRST move of that puzzle's curated Lichess line — the
  database is authoritative for the answer; nothing is invented and no
  engine replaces it. ``Puzzle.fen`` stays NULL and ``position_json``
  carries only the description/side/mode/piece count.
- position_json: {"description_fa": "...", "side_to_move": "white"|"black",
  "mode": "best-move", "piece_count": N} (visible to frontend).

Attempt model (sent by client):
    {"move": "Nf3"}

Correctness is authoritative, never a string comparison: the submitted
SAN is parsed with ``board.parse_san`` against the stored position,
normalized to UCI, and counts as CORRECT only when that UCI equals the
stored solution. Any extra client data (fen, solution, score, timing)
is ignored.

Legacy rows (answer_json with "example"/"mate_count" and no "solution",
from the earlier mate-in-1 prototype) keep their original rule — CORRECT
only for a legal checkmating move — so existing databases keep working.

Result rules: CORRECT or WRONG only (a single move cannot be partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "blindfold-calculation"


def solution_san(fen: str, solution_uci: str) -> str:
    """Canonical SAN for the stored solution (used for feedback/detail).

    Falls back to the raw UCI text when the stored row is corrupt, so a
    bad row still fails safe instead of breaking the API.
    """
    try:
        board = chess.Board(fen)
        return board.san(chess.Move.from_uci(solution_uci))
    except (ValueError, AssertionError):
        return solution_uci if isinstance(solution_uci, str) else ""


def mating_sans(fen: str) -> list[str]:
    """All mating moves in canonical SAN form (legacy rows + tests)."""
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


def mating_moves(fen: str) -> list[str]:
    """All mating moves in UCI form (legacy rows + tests)."""
    board = chess.Board(fen)  # raises on invalid FEN
    found: list[str] = []
    for move in board.legal_moves:
        board.push(move)
        try:
            if board.is_checkmate():
                found.append(board.peek().uci())
        finally:
            board.pop()
    return sorted(found)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    fen = answer.get("fen")
    solution = answer.get("solution")
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

    # Legacy mate-in-1 rows (no "solution" key) keep the original rule:
    # CORRECT only when the move is legal AND produces checkmate.
    if not isinstance(solution, str) or not solution:
        return _validate_legacy_mate(answer, submitted, wrong)

    if not isinstance(fen, str) or not submitted:
        expected = solution_san(fen, solution) if isinstance(fen, str) else ""
        return wrong([expected] if expected else [])

    try:
        board = chess.Board(fen)
    except ValueError:
        return wrong([])

    try:
        move = board.parse_san(submitted)
    except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError, ValueError):
        try:
            expected = solution_san(fen, solution)
        except ValueError:
            expected = ""
        return wrong([expected] if expected else [])

    # Move identity is the UCI on the real board, never the SAN string:
    # "Nf3" and "Nf3+" denote the same move when both parse to it.
    if move.uci() == solution:
        canonical = board.san(move)
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": [canonical], "missed": [], "wrong": [], "correct_move": canonical},
        )
    try:
        expected = solution_san(fen, solution)
    except ValueError:
        expected = ""
    return wrong([expected] if expected else [])


def _validate_legacy_mate(
    answer: dict[str, Any], submitted: str, wrong
) -> ValidationResult:
    """Original mate-in-1 rule for legacy rows (no stored solution)."""
    fen = answer.get("fen")

    if not isinstance(fen, str) or not submitted:
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
