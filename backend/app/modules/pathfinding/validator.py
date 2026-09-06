"""Pathfinding rules (Exercise 6, simple version).

One white piece (knight/bishop/rook/queen) walks step by step toward a
star square on an otherwise EMPTY board. A step is allowed iff it is one
legal move of that piece's real chess movement with no blockers
(see ``moves.py``). There is no king on the board, so there is no
king-safety, check, attack-map or capture concept in this exercise —
those belong to Exercise 7 (obstacles), implemented separately.

Puzzle definition (stored in the puzzle row, server-side only):
- ``Puzzle.fen``: empty board with the single white piece (rendering).
- ``position_json``: {"from", "target", "piece"} (public task data).
- ``answer_json``: {"fen", "from", "target", "piece", "optimal_moves"}
  (never exposed; ``optimal_moves`` is the BFS minimum).

Attempt model (sent by the client):
- {"path": ["e2", "e4", ...], "illegal_attempts": 2}
  ``path`` starts at ``from`` and lists every square the piece stood on
  (path[0] == from, len(path) - 1 == actual legal moves).
  ``illegal_attempts`` counts rejected drag/click tries client-side.

Validation: CORRECT iff every consecutive step is legal geometry for the
stored piece AND the path ends exactly on the target. Anything else
(incomplete path, illegal step, wrong start, malformed input, claiming
completion from another square) is WRONG. There is no PARTIAL: reaching
the star is the submission event. Any legal route with the optimal move
count scores as optimal — no specific BFS route is ever enforced.
"""

from __future__ import annotations

from typing import Any

from app.modules.pathfinding import moves
from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "pathfinding"


def _illegal_count(raw: Any) -> int:
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int) and raw > 0:
        return raw
    return 0


def replay_path(kind: str, start: str, target: str, path: list[str]) -> dict[str, Any]:
    """Replay a path with pure movement geometry.

    Returns {"ok", "prefix", "fail_at", "reached", "moves"}. Never raises
    on bad squares (they fail the replay); raises ValueError only for an
    unknown piece kind.
    """
    if kind not in moves.ALLOWED_KINDS:
        raise ValueError("unknown_piece_kind")
    prefix = [path[0]] if path else []
    current = path[0] if path else start
    for square in path[1:]:
        if not moves.is_legal_step(kind, current, square):
            return {
                "ok": False,
                "prefix": prefix,
                "fail_at": square,
                "reached": False,
                "moves": len(prefix) - 1,
            }
        current = square
        prefix.append(square)
    reached = bool(path) and current == target
    return {
        "ok": reached,
        "prefix": prefix,
        "fail_at": None if reached else target,
        "reached": reached,
        "moves": max(0, len(prefix) - 1),
    }


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    start = normalize_square(answer.get("from"))
    target = normalize_square(answer.get("target"))
    raw_kind = answer.get("piece")
    kind = raw_kind.strip().lower() if isinstance(raw_kind, str) else None
    optimal = answer.get("optimal_moves")
    optimal_n = optimal if isinstance(optimal, int) and optimal >= 0 else None

    def wrong(detail_extra: dict[str, Any] | None = None) -> ValidationResult:
        detail: dict[str, Any] = {
            "correct": [],
            "missed": [target] if target else [],
            "wrong": [],
            "reached": False,
            "moves": 0,
            "optimal_moves": optimal_n if optimal_n is not None else 0,
            "illegal_attempts": 0,
        }
        if detail_extra:
            detail.update(detail_extra)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)

    if start is None or target is None or kind not in moves.ALLOWED_KINDS or optimal_n is None:
        return wrong()
    raw = attempt.get("path") if isinstance(attempt, dict) else None
    if not isinstance(raw, list) or not raw:
        return wrong()
    path: list[str] = []
    for entry in raw:
        square = normalize_square(entry)
        if square is None:
            return wrong({"wrong": [str(entry)]})
        path.append(square)
    if path[0] != start:
        return wrong({"wrong": [path[0]]})
    illegal = _illegal_count(attempt.get("illegal_attempts") if isinstance(attempt, dict) else 0)
    try:
        run = replay_path(kind, start, target, path)
    except ValueError:
        return wrong()
    base = {
        "optimal_moves": optimal_n,
        "illegal_attempts": illegal,
        "moves": run["moves"],
        "path": run["prefix"],
    }
    if run["ok"]:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={
                "correct": run["prefix"],
                "missed": [],
                "wrong": [],
                "reached": True,
                **base,
            },
        )
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={
            "correct": run["prefix"],
            "missed": [] if run["reached"] else [target],
            "wrong": [run["fail_at"]] if run["fail_at"] else [],
            "reached": run["reached"],
            **base,
        },
    )


# --- Single-step assistance (used by POST /pathfinding/step) ---


def apply_step(kind: str, origin: str, dest: str) -> str | None:
    """One-step oracle: the destination square when legal, else None.

    Pure geometry, no board state: on the empty board every legal step is
    always available regardless of history. Raises ValueError on unknown
    piece kind.
    """
    if kind not in moves.ALLOWED_KINDS:
        raise ValueError("unknown_piece_kind")
    origin_sq = normalize_square(origin)
    dest_sq = normalize_square(dest)
    if origin_sq is None or dest_sq is None or origin_sq == dest_sq:
        return None
    if not moves.is_legal_step(kind, origin_sq, dest_sq):
        return None
    return dest_sq


def mover_kind(answer: dict[str, Any]) -> str:
    """Piece kind stored in the puzzle answer. Raises ValueError when bad."""
    raw = answer.get("piece") if isinstance(answer, dict) else None
    kind = raw.strip().lower() if isinstance(raw, str) else ""
    if kind not in moves.ALLOWED_KINDS:
        raise ValueError("unknown_piece_kind")
    return kind
