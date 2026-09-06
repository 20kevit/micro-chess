"""Pathfinding-with-obstacles validation (Exercise 7).

One white piece (knight/bishop/rook/queen) walks step by step toward a
star square while black enemies block rays, control destinations, and
can be captured when undefended. Captures change the board, so the path
is replayed STATEFULLY through ``transitions``: the same authoritative
layer used by the solver, the generator, and the single-step oracle.

Puzzle definition (stored in the puzzle row, server-side only):
- ``Puzzle.fen``: full position (white mover + black enemies, rendering).
- ``position_json``: {"from", "target", "piece", "enemies": [{square, kind}]}
  (public task data).
- ``answer_json``: position fields + ``optimal_moves`` (BFS minimum, never
  exposed; any route with exactly that many moves is optimal).

Attempt model (sent by the client):
- {"path": ["e2", "e4", ...], "illegal_attempts": 2}
  ``path`` starts at ``from`` and lists every square the piece stood on
  (path[0] == from, len(path) - 1 == actual legal moves, captures count
  as one legal move each).
  ``illegal_attempts`` counts rejected drag/click tries client-side.

Validation: CORRECT iff every consecutive step is a legal transition of
the CURRENT state (movement + blocking + destination safety + capture
rules, with enemy state updated after each capture) AND the path ends
exactly on the target. Anything else is WRONG. There is no PARTIAL:
reaching the star is the submission event.
"""

from __future__ import annotations

from typing import Any

from app.modules.pathfinding_obstacles import transitions as tr
from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "pathfinding-obstacles"


def _illegal_count(raw: Any) -> int:
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int) and raw > 0:
        return raw
    return 0


def _answer_state(puzzle_answer: dict[str, Any]) -> tr.State | None:
    try:
        return tr.parse_state(puzzle_answer)
    except ValueError:
        return None


def replay_path(
    state: tr.State, path: list[str]
) -> dict[str, Any]:
    """Replay a path statefully from ``state``.

    Returns {"ok", "prefix", "fail_at", "reached", "moves", "captures"}.
    Never raises on bad squares (they fail the replay).
    """
    prefix = [path[0]] if path else []
    current = state
    captures = 0
    for square in path[1:]:
        nxt = tr.apply_move(current, square)
        if nxt is None:
            return {
                "ok": False,
                "prefix": prefix,
                "fail_at": square,
                "reached": False,
                "moves": len(prefix) - 1,
                "captures": captures,
            }
        if len(nxt.enemies) < len(current.enemies):
            captures += 1
        current = nxt
        prefix.append(square)
    reached = bool(path) and current.white_square == current.target
    return {
        "ok": reached,
        "prefix": prefix,
        "fail_at": None if reached else current.target,
        "reached": reached,
        "moves": max(0, len(prefix) - 1),
        "captures": captures,
    }


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    optimal = answer.get("optimal_moves")
    optimal_n = optimal if isinstance(optimal, int) and optimal >= 0 else None

    def wrong(detail_extra: dict[str, Any] | None = None) -> ValidationResult:
        detail: dict[str, Any] = {
            "correct": [],
            "missed": [],
            "wrong": [],
            "reached": False,
            "moves": 0,
            "optimal_moves": optimal_n if optimal_n is not None else 0,
            "illegal_attempts": 0,
        }
        if detail_extra:
            detail.update(detail_extra)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)

    state = _answer_state(answer)
    if state is None or optimal_n is None:
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
    if path[0] != state.white_square:
        return wrong({"wrong": [path[0]]})
    illegal = _illegal_count(attempt.get("illegal_attempts") if isinstance(attempt, dict) else 0)
    run = replay_path(state, path)
    base = {
        "optimal_moves": optimal_n,
        "illegal_attempts": illegal,
        "moves": run["moves"],
        "path": run["prefix"],
        "captures": run["captures"],
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
            "missed": [] if run["reached"] else [state.target],
            "wrong": [run["fail_at"]] if run["fail_at"] else [],
            "reached": run["reached"],
            **base,
        },
    )


# --- Single-step assistance (used by POST /pathfinding-obstacles/step) ---


def apply_step(state: tr.State, origin: str, dest: str) -> tr.State | None:
    """One-step oracle on the LIVE state (captures included).

    Returns the resulting state when legal, else None. The caller
    reconstructs ``state`` from the client FEN (current enemies included)
    and the server-stored kind/target, so mid-puzzle captures are honored.
    """
    origin_sq = normalize_square(origin)
    dest_sq = normalize_square(dest)
    if origin_sq is None or dest_sq is None or origin_sq == dest_sq:
        return None
    if origin_sq != state.white_square:
        return None
    if origin_sq == state.target:
        # Star already reached: the puzzle is complete, no further moves.
        return None
    return tr.apply_move(state, dest_sq)


def mover_kind(answer: dict[str, Any]) -> str:
    """Piece kind stored in the puzzle answer. Raises ValueError when bad."""
    raw = answer.get("piece") if isinstance(answer, dict) else None
    kind = raw.strip().lower() if isinstance(raw, str) else ""
    if kind not in tr.ALLOWED_WHITE_KINDS:
        raise ValueError("unknown_piece_kind")
    return kind
