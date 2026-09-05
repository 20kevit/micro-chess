"""Blindfold Opening Traps validator: one correct tactical move, eyes closed.

MVP scope: a single tactical move from a genuine opening-trap position.
Unlike Mate in 1, checkmate is NOT required. Unlike string matching, the
submitted SAN is parsed with ``board.parse_san`` against the stored
position and normalized to UCI; it counts as CORRECT only when that UCI
belongs to the puzzle's explicit solution set. Puzzles may (and some do)
accept several different winning moves.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "solutions": ["e2e4", ...], "theme": "FORK"}.
  The FEN and the solution UCIs must live here because validators only
  receive answer_json. The ``Puzzle.fen`` column stays NULL and
  ``position_json`` carries only solving-safe text (see description.py).
- position_json: {"description_fa": "...", "side_to_move": "white"|"black",
  "mode": "tactic-1", "opening_fa": "...", "trap_fa": "...",
  "theme": "FORK", "theme_fa": "..."} (visible to frontend).

Attempt model (sent by client):
    {"move": "Nxf7"}

Result rules: CORRECT or WRONG only (a single move cannot be partial).
Malformed, illegal, ambiguous, empty, and legal-but-not-tactical input
fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "opening-traps"


def solution_sans(fen: str, solutions: list[str]) -> list[str]:
    """Canonical SANs for stored solution UCIs (used for feedback/detail).

    Never crashes: unparseable stored entries fall back to their UCI text
    so a corrupt row still fails safe as WRONG instead of breaking the API.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    sans: list[str] = []
    for uci in solutions:
        try:
            sans.append(board.san(chess.Move.from_uci(uci)))
        except (ValueError, AssertionError):
            sans.append(uci if isinstance(uci, str) else "?")
    return sorted(sans)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    fen = answer.get("fen")
    raw_solutions = answer.get("solutions")
    theme = answer.get("theme") if isinstance(answer.get("theme"), str) else ""
    raw_move = attempt_map.get("move")

    solutions = [s for s in raw_solutions] if isinstance(raw_solutions, list) else []
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
                "theme": theme,
            },
        )

    # Anything the client sends (fen, solutions, theme, flags) is ignored;
    # only the stored answer and the submitted move string are used.
    if not isinstance(fen, str) or not submitted or not solutions:
        try:
            expected = solution_sans(fen, solutions) if isinstance(fen, str) else []
        except ValueError:
            expected = []
        return wrong([expected[0]] if expected else [])

    try:
        board = chess.Board(fen)
    except ValueError:
        return wrong([])

    try:
        move = board.parse_san(submitted)
    except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError, ValueError):
        try:
            expected = solution_sans(fen, solutions)
        except ValueError:
            expected = []
        return wrong([expected[0]] if expected else [])

    # Move identity is the UCI on the real board, never the SAN string:
    # "Qxf7" and "Qxf7+" denote the same move when both parse to it.
    if move.uci() in {s for s in solutions if isinstance(s, str)}:
        canonical = board.san(move)
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": [canonical], "missed": [], "wrong": [], "correct_move": canonical, "theme": theme},
        )
    try:
        expected = solution_sans(fen, solutions)
    except ValueError:
        expected = []
    return wrong([expected[0]] if expected else [])
