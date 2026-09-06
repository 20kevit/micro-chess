"""Simple pathfinding movement geometry (Exercise 6).

Exercise 6 is intentionally the SIMPLE pathfinding version: exactly one
white piece (knight/bishop/rook/queen) on an otherwise empty board plus a
star/target square. There is no white king, no black pieces, no obstacles
and no captures. Movement is pure piece geometry on the empty board:

- knight: the 8 L-jumps (jumps, nothing blocks);
- bishop: any diagonal distance (no blockers);
- rook: any horizontal/vertical distance (no blockers);
- queen: union of rook + bishop.

There is deliberately NO king-safety concept here: no king exists on the
board, so no move can expose a king and no destination can be "attacked".
``python-chess`` is not used for legality on purpose — an empty board
without kings is not a legal chess position, but movement GEOMETRY is
still exactly the piece's real chess movement. The independent test suite
recomputes distances with raw ``python-chess`` on a kingless board to
guard the graph.

Graph model: node = square, edge = one legal move of the selected piece.
``shortest_path_length`` is BFS over that graph and minimizes the NUMBER
OF PIECE MOVES (never the number of squares traveled).
"""

from __future__ import annotations

from collections import deque

ALLOWED_KINDS = ("knight", "bishop", "rook", "queen")

# Generator target distribution (documented in docs/exercises/06-pathfinding.md).
PIECE_WEIGHTS: dict[str, float] = {
    "knight": 0.50,
    "bishop": 0.20,
    "rook": 0.20,
    "queen": 0.10,
}

PIECE_LETTER: dict[str, str] = {
    "knight": "N",
    "bishop": "B",
    "rook": "R",
    "queen": "Q",
}

_FILES = "abcdefgh"


def _to_xy(square: str) -> tuple[int, int]:
    return _FILES.index(square[0]), int(square[1]) - 1


def _to_square(x: int, y: int) -> str:
    return f"{_FILES[x]}{y + 1}"


def _on_board(x: int, y: int) -> bool:
    return 0 <= x < 8 and 0 <= y < 8


_KNIGHT_OFFSETS = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))
_ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _slide(x: int, y: int, dirs: tuple[tuple[int, int], ...]) -> set[str]:
    out: set[str] = set()
    for dx, dy in dirs:
        nx, ny = x + dx, y + dy
        while _on_board(nx, ny):
            out.add(_to_square(nx, ny))
            nx += dx
            ny += dy
    return out


def legal_dests(kind: str, square: str) -> set[str]:
    """All squares reachable in ONE legal move from ``square``.

    Raises ValueError on unknown kind or malformed square.
    """
    if kind not in ALLOWED_KINDS:
        raise ValueError("unknown_piece_kind")
    sq = square.strip().lower()
    if len(sq) != 2 or sq[0] not in _FILES or sq[1] not in "12345678":
        raise ValueError("invalid_square")
    x, y = _to_xy(sq)
    if kind == "knight":
        return {_to_square(x + dx, y + dy) for dx, dy in _KNIGHT_OFFSETS if _on_board(x + dx, y + dy)}
    if kind == "rook":
        return _slide(x, y, _ROOK_DIRS)
    if kind == "bishop":
        return _slide(x, y, _BISHOP_DIRS)
    return _slide(x, y, _ROOK_DIRS + _BISHOP_DIRS)


def is_legal_step(kind: str, origin: str, dest: str) -> bool:
    """True when ``origin -> dest`` is one legal move for ``kind``."""
    try:
        if origin.strip().lower() == dest.strip().lower():
            return False
        return dest.strip().lower() in legal_dests(kind, origin)
    except ValueError:
        return False


def shortest_path_length(kind: str, start: str, target: str) -> int | None:
    """Minimum number of piece moves from ``start`` to ``target``.

    BFS over (square) nodes. Returns None when unreachable — on the empty
    board that only happens for a bishop whose target is on the opposite
    square color. Raises ValueError on bad input.
    """
    start_sq = start.strip().lower()
    target_sq = target.strip().lower()
    if kind not in ALLOWED_KINDS:
        raise ValueError("unknown_piece_kind")
    for sq in (start_sq, target_sq):
        if len(sq) != 2 or sq[0] not in _FILES or sq[1] not in "12345678":
            raise ValueError("invalid_square")
    if start_sq == target_sq:
        return 0
    seen = {start_sq}
    queue: deque[tuple[str, int]] = deque([(start_sq, 0)])
    while queue:
        pos, dist = queue.popleft()
        for nxt in legal_dests(kind, pos):
            if nxt == target_sq:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return None
