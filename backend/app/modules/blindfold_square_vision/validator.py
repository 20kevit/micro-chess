"""Blindfold Square Vision validator: minimum moves on an empty board.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"piece": "N", "color": "white", "from": "a1", "to": "c2"}.
  Task parameters only — never the solution. Correctness is always
  recomputed from the position, never from a stored move count.

Attempt model (sent by client):
    {"moves": 3}

There are no blocking pieces, no check, no captures and no opponent: only
the movement geometry of the selected piece matters. Kings, queens, rooks
and bishops use closed-form distances; knights and pawns use BFS over the
empty 8x8 board (pawns move forward only, single and double pushes from
their start rank, never backward or sideways).

Result rules: CORRECT or WRONG only. Malformed input fails safely as WRONG
and never crashes the API.
"""

from collections import deque
from typing import Any

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "blindfold-square-vision"

_PIECES = ("K", "Q", "R", "B", "N", "P")
_COLORS = ("white", "black")

_KNIGHT_STEPS = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))


def _coords(square: str) -> tuple[int, int]:
    """Square name to (file, rank) with 0-based indices."""
    return ord(square[0]) - ord("a"), int(square[1]) - 1


def _on_board(file: int, rank: int) -> bool:
    return 0 <= file < 8 and 0 <= rank < 8


def normalize_piece(raw: Any) -> str | None:
    """Uppercase/validate a piece letter. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    piece = raw.strip().upper()
    return piece if piece in _PIECES else None


def normalize_color(raw: Any) -> str | None:
    """Lowercase/validate a color name. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    color = raw.strip().lower()
    return color if color in _COLORS else None


def normalize_moves(raw: Any) -> int | None:
    """Validate a submitted move count. Only non-negative ints, never bools."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw if raw >= 0 else None


def king_distance(origin: str, dest: str) -> int:
    """Chebyshev distance: one square per move in any direction."""
    fx, fr = _coords(origin)
    tx, tr = _coords(dest)
    return max(abs(tx - fx), abs(tr - fr))


def rook_distance(origin: str, dest: str) -> int:
    """Same rank/file in 1, anywhere else in 2, same square in 0."""
    if origin == dest:
        return 0
    return 1 if origin[0] == dest[0] or origin[1] == dest[1] else 2


def bishop_distance(origin: str, dest: str) -> int | None:
    """Same diagonal in 1 (0 if same square); None when unreachable.

    A bishop stays on its square color: same color and not aligned means
    exactly 2, opposite colors means unreachable.
    """
    if origin == dest:
        return 0
    fx, fr = _coords(origin)
    tx, tr = _coords(dest)
    if abs(tx - fx) == abs(tr - fr):
        return 1
    if (fx + fr) % 2 == (tx + tr) % 2:
        return 2
    return None


def queen_distance(origin: str, dest: str) -> int:
    """Same rank, file or diagonal in 1 (0 if same); otherwise 2."""
    if origin == dest:
        return 0
    fx, fr = _coords(origin)
    tx, tr = _coords(dest)
    if fx == tx or fr == tr or abs(tx - fx) == abs(tr - fr):
        return 1
    return 2


def _bfs_distance(moves_from: Any, origin: str, dest: str) -> int | None:
    """Generic shortest-path BFS used by knights and pawns."""
    if origin == dest:
        return 0
    seen = {origin}
    queue: deque[tuple[str, int]] = deque([(origin, 0)])
    while queue:
        square, dist = queue.popleft()
        for nxt in moves_from(square):
            if nxt == dest:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return None


def _knight_targets(square: str) -> list[str]:
    fx, fr = _coords(square)
    return [
        chr(ord("a") + fx + dx) + str(fr + dy + 1)
        for dx, dy in _KNIGHT_STEPS
        if _on_board(fx + dx, fr + dy)
    ]


def knight_distance(origin: str, dest: str) -> int | None:
    """True minimum knight distance via BFS (always reachable)."""
    result = _bfs_distance(_knight_targets, origin, dest)
    assert result is not None  # knights reach every square
    return result


def _pawn_targets(color: str, square: str) -> list[str]:
    """Forward pushes only: single step, plus double step from start rank."""
    fx, fr = _coords(square)
    step = 1 if color == "white" else -1
    start_rank = 1 if color == "white" else 6
    targets = []
    if _on_board(fx, fr + step):
        targets.append(chr(ord("a") + fx) + str(fr + step + 1))
    if fr == start_rank and _on_board(fx, fr + 2 * step):
        targets.append(chr(ord("a") + fx) + str(fr + 2 * step + 1))
    return targets


def pawn_distance(color: str, origin: str, dest: str) -> int | None:
    """Forward-only pawn distance; None when backward, sideways or stuck."""
    return _bfs_distance(lambda sq: _pawn_targets(color, sq), origin, dest)


def min_moves(piece: str, color: str, origin: str, dest: str) -> int | None:
    """Minimum moves for a validated task, or None when unreachable."""
    if piece == "K":
        return king_distance(origin, dest)
    if piece == "Q":
        return queen_distance(origin, dest)
    if piece == "R":
        return rook_distance(origin, dest)
    if piece == "B":
        return bishop_distance(origin, dest)
    if piece == "N":
        return knight_distance(origin, dest)
    return pawn_distance(color, origin, dest)


def example_path(piece: str, color: str, origin: str, dest: str) -> list[str] | None:
    """One valid shortest path (for post-submit feedback), or None."""
    if origin == dest:
        return [origin]
    if piece == "K":
        # Walk one square at a time toward the target.
        path = [origin]
        fx, fr = _coords(origin)
        tx, tr = _coords(dest)
        while (fx, fr) != (tx, tr):
            fx += (tx > fx) - (tx < fx)
            fr += (tr > fr) - (tr < fr)
            path.append(chr(ord("a") + fx) + str(fr + 1))
        return path
    if piece in ("K", "Q", "R", "B"):
        return _aligned_path(piece, origin, dest)
    # Knights and pawns: recover a BFS path.
    moves_from = _knight_targets if piece == "N" else (lambda sq: _pawn_targets(color, sq))
    prev: dict[str, str | None] = {origin: None}
    queue: deque[str] = deque([origin])
    while queue:
        square = queue.popleft()
        for nxt in moves_from(square):
            if nxt not in prev:
                prev[nxt] = square
                queue.append(nxt)
    if dest not in prev:
        return None
    path = [dest]
    while path[-1] != origin:
        parent = prev[path[-1]]
        assert parent is not None
        path.append(parent)
    path.reverse()
    if piece == "B" and len(path) - 1 != 2:
        return None
    return path


def _aligned_path(piece: str, origin: str, dest: str) -> list[str] | None:
    """Direct two-point path for aligned sliders, midpoint for 2-move cases."""
    dist = min_moves(piece, "white", origin, dest)
    if dist is None:
        return None
    if dist <= 1:
        return [origin, dest] if origin != dest else [origin]
    fx, fr = _coords(origin)
    tx, tr = _coords(dest)
    if piece == "R":
        via = chr(ord("a") + tx) + str(fr + 1)
        return [origin, via, dest]
    if piece == "Q":
        # Queens always reach in 2 via an aligned intermediate square.
        for cand_rank in range(8):
            via = chr(ord("a") + tx) + str(cand_rank + 1)
            if queen_distance(origin, via) == 1 and queen_distance(via, dest) == 1:
                return [origin, via, dest]
        for cand_file in range(8):
            via = chr(ord("a") + cand_file) + str(tr + 1)
            if queen_distance(origin, via) == 1 and queen_distance(via, dest) == 1:
                return [origin, via, dest]
        return None
    # Bishop 2-move case: intersect the two diagonals through origin/dest.
    for dfx, dfr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        fx2, fr2 = fx + dfx, fr + dfr
        while _on_board(fx2, fr2):
            via = chr(ord("a") + fx2) + str(fr2 + 1)
            if bishop_distance(via, dest) == 1:
                return [origin, via, dest]
            fx2 += dfx
            fr2 += dfr
    return None


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    piece = normalize_piece(puzzle_answer.get("piece") if isinstance(puzzle_answer, dict) else None)
    color = normalize_color(puzzle_answer.get("color") if isinstance(puzzle_answer, dict) else None)
    origin = normalize_square(puzzle_answer.get("from") if isinstance(puzzle_answer, dict) else None)
    dest = normalize_square(puzzle_answer.get("to") if isinstance(puzzle_answer, dict) else None)
    submitted = normalize_moves(attempt.get("moves") if isinstance(attempt, dict) else None)

    if piece is None or color is None or origin is None or dest is None or submitted is None:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": []},
        )
    expected = min_moves(piece, color, origin, dest)
    if expected is None:
        # Unreachable pairs must never be presented; fail closed regardless.
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": [str(submitted)]},
        )
    path = example_path(piece, color, origin, dest) or []
    if submitted == expected:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": [str(submitted)], "missed": [], "wrong": [], "moves": expected, "path": path},
        )
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={"correct": [], "missed": [], "wrong": [str(submitted)], "moves": expected, "path": path},
    )
