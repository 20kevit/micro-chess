"""Authoritative state-transition layer for Exercise 7 (Pathfinding with Obstacles).

Single source of truth for movement rules, used by the runtime validator,
the single-step oracle, the BFS solver, and the generator. There are no
parallel implementations: every consumer calls into this module.

State model
-----------
A state is the complete board situation, NOT just the white square::

    State { white kind, white square, remaining black pieces, star square }

Two states with the same white square but different remaining enemies are
different states and must never be collapsed into one visited node.

Rules (enforced identically everywhere)
---------------------------------------
- The white piece (knight/bishop/rook/queen) moves with normal chess
  movement; enemy pieces physically block sliding rays (knights jump).
- The white piece may NEVER LAND on a square controlled by an enemy piece.
  Only the destination square matters: for sliders, enemy control of an
  intermediate square does not make the move illegal (physical occupancy
  still blocks the path).
- A black piece may be captured only when it is UNDEFENDED (zero other
  black pieces attack its square; no pin filtering, no kings exist) AND
  the destination square itself is not controlled by ANY black piece.
- After every capture the captured piece disappears and enemy
  attacks/defenders are recomputed from the resulting position. Attack
  maps are therefore per-state, never precomputed once for a puzzle.
- Destination safety is evaluated on the RESULTING position (white piece
  already on the destination, captured piece already removed). This is
  what makes the capture's Condition B independent from Condition A:
  the white piece's own departure can uncover a black ray onto the
  destination (e.g. a white rook shielding its landing square from a
  black rook behind it). In that case the pre-move square looks safe
  but the landing square is controlled, so the move is illegal.

Implementation notes
--------------------
- Standard chess geometry/blocking comes from ``python-chess`` on a
  kingless board (movement + ``attackers`` need no kings). Exercise
  rules (destination safety, undefended-only captures) live here.
- ``board.attackers`` never counts the occupant of the queried square,
  so defender/attack queries need no self-exclusion beyond ignoring the
  square being removed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import chess

ALLOWED_WHITE_KINDS = ("knight", "bishop", "rook", "queen")
ALLOWED_ENEMY_KINDS = ("pawn", "knight", "bishop", "rook", "queen")

WHITE_LETTER: dict[str, str] = {
    "knight": "N",
    "bishop": "B",
    "rook": "R",
    "queen": "Q",
}

ENEMY_LETTER: dict[str, str] = {
    "pawn": "p",
    "knight": "n",
    "bishop": "b",
    "rook": "r",
    "queen": "q",
}

LETTER_TO_ENEMY: dict[str, str] = {v: k for k, v in ENEMY_LETTER.items()}


def _norm_square(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    sq = raw.strip().lower()
    if len(sq) != 2 or sq[0] not in "abcdefgh" or sq[1] not in "12345678":
        return None
    return sq


def _norm_kind(raw: Any, allowed: tuple[str, ...]) -> str | None:
    if not isinstance(raw, str):
        return None
    kind = raw.strip().lower()
    return kind if kind in allowed else None


@dataclass(frozen=True)
class State:
    """Complete puzzle situation. Hashable; equality covers white square AND enemies."""

    white_kind: str
    white_square: str
    # Sorted ((square, kind), ...) so equivalent states hash identically.
    enemies: tuple[tuple[str, str], ...]
    target: str

    def key(self) -> tuple:
        return (self.white_kind, self.white_square, self.enemies, self.target)


def canonical_key(state: State) -> tuple:
    """Stable hashable encoding of a state (used for BFS visited sets)."""
    return state.key()


def parse_state(data: dict[str, Any]) -> State:
    """Build a State from stored dicts. Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("invalid_state")
    kind = _norm_kind(data.get("piece"), ALLOWED_WHITE_KINDS)
    white = _norm_square(data.get("from", data.get("white")))
    target = _norm_square(data.get("target"))
    if kind is None or white is None or target is None:
        raise ValueError("invalid_state")
    raw_enemies = data.get("enemies", [])
    if not isinstance(raw_enemies, list):
        raise ValueError("invalid_state")
    enemies: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in raw_enemies:
        if not isinstance(entry, dict):
            raise ValueError("invalid_state")
        sq = _norm_square(entry.get("square"))
        ekind = _norm_kind(entry.get("kind"), ALLOWED_ENEMY_KINDS)
        if sq is None or ekind is None or sq in seen:
            raise ValueError("invalid_state")
        seen.add(sq)
        enemies.append((sq, ekind))
    enemies.sort()
    return State(white_kind=kind, white_square=white, enemies=tuple(enemies), target=target)


def state_to_dict(state: State) -> dict[str, Any]:
    return {
        "piece": state.white_kind,
        "from": state.white_square,
        "target": state.target,
        "enemies": [{"square": sq, "kind": kind} for sq, kind in state.enemies],
    }


def build_board(state: State, *, without: str | None = None) -> chess.Board:
    """Kingless board for ``state``; ``without`` omits one enemy square.

    Used to evaluate the position AFTER a capture (the captured piece no
    longer attacks or defends anything).
    """
    board = chess.Board.empty()
    board.set_piece_at(
        chess.parse_square(state.white_square),
        chess.Piece.from_symbol(WHITE_LETTER[state.white_kind]),
    )
    for sq, kind in state.enemies:
        if sq == without:
            continue
        board.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(ENEMY_LETTER[kind]))
    board.turn = chess.WHITE
    return board


def black_attackers(state: State, square: str, *, without: str | None = None) -> set[str]:
    """Black-occupied squares attacking ``square`` in this state.

    Raw attack geometry (no pin filtering: no kings exist). The occupant
    of ``square`` itself is never reported by ``board.attackers``.
    """
    board = build_board(state, without=without)
    target = chess.parse_square(square)
    return {chess.square_name(sq) for sq in board.attackers(chess.BLACK, target)}


def is_undefended(state: State, square: str) -> bool:
    """True when no OTHER black piece attacks ``square`` (capture Condition A)."""
    return not black_attackers(state, square)


def is_safe_destination(state: State, square: str, *, without: str | None = None) -> bool:
    """True when no black piece controls ``square`` on the CURRENT board
    (minus ``without``). Raw per-state query used by tests/generator; the
    move legality check itself evaluates safety on the POST-MOVE board
    (see ``legal_transitions``)."""
    return not black_attackers(state, square, without=without)


def _post_move_board(state: State, dest: str, *, captured: str | None) -> chess.Board:
    """Board AFTER the white move: white already on ``dest``, the captured
    enemy (if any) already removed, everything else unchanged."""
    board = build_board(state, without=captured)
    board.remove_piece_at(chess.parse_square(state.white_square))
    board.set_piece_at(
        chess.parse_square(dest),
        chess.Piece.from_symbol(WHITE_LETTER[state.white_kind]),
    )
    return board


def _post_move_safe(state: State, dest: str, *, captured: str | None) -> bool:
    """Capture Condition B / landing rule: the destination is uncontrolled
    in the resulting position. Catches uncoverings where the white piece's
    own departure opens a black ray onto the landing square."""
    board = _post_move_board(state, dest, captured=captured)
    return not board.attackers(chess.BLACK, chess.parse_square(dest))


def _pseudo_dests(board: chess.Board, origin: chess.Square) -> dict[chess.Square, bool]:
    """Pseudo-legal destinations from ``origin`` mapped to is-capture.

    Pseudo-legal (not legal) on purpose: the kingless board has no king
    safety to preserve, and there are no kings at all in this exercise.
    Sliding rays stop at the first occupied square (physical blocking);
    knights jump.
    """
    out: dict[chess.Square, bool] = {}
    for move in board.pseudo_legal_moves:
        if move.from_square != origin:
            continue
        out[move.to_square] = board.is_capture(move)
    return out


def legal_transitions(state: State) -> dict[str, dict[str, Any]]:
    """All valid white moves from ``state``: dest square -> transition info.

    ``{"capture": bool, "captured": square|None}``. A move is valid iff:
    - it follows normal movement/blocking (pseudo-legal from the origin);
    - for captures, the victim has zero black defenders on the CURRENT
      board (Condition A);
    - the destination is uncontrolled on the RESULTING board, i.e. after
      the white piece has landed and a captured piece has been removed
      (Condition B / landing rule). The white departure can uncover a
      black ray, so the pre-move attack map alone is not sufficient.
    Intermediate-square control is deliberately ignored for sliders.
    """
    board = build_board(state)
    origin = chess.parse_square(state.white_square)
    if board.piece_at(origin) is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for dest_sq, is_capture in _pseudo_dests(board, origin).items():
        dest = chess.square_name(dest_sq)
        if is_capture:
            # Condition A: the victim must have zero black defenders.
            if not is_undefended(state, dest):
                continue
            # Condition B: landing square uncontrolled after the capture.
            if not _post_move_safe(state, dest, captured=dest):
                continue
            result[dest] = {"capture": True, "captured": dest}
        else:
            if not _post_move_safe(state, dest, captured=None):
                continue
            result[dest] = {"capture": False, "captured": None}
    return result


def apply_move(state: State, dest_raw: str) -> State | None:
    """Next state after moving to ``dest``; None when the move is illegal."""
    dest = _norm_square(dest_raw)
    if dest is None or dest == state.white_square:
        return None
    transitions = legal_transitions(state)
    info = transitions.get(dest)
    if info is None:
        return None
    if info["capture"]:
        remaining = tuple((sq, kind) for sq, kind in state.enemies if sq != dest)
    else:
        remaining = state.enemies
    return State(
        white_kind=state.white_kind,
        white_square=dest,
        enemies=remaining,
        target=state.target,
    )


def fen_for_state(state: State) -> str:
    """Render the state as FEN (white mover + remaining black pieces)."""
    board = build_board(state)
    board.set_castling_fen("-")
    board.ep_square = None
    board.halfmove_clock = 0
    board.fullmove_number = 1
    return board.fen()


def state_from_fen(
    fen: str, *, white_kind: str, target: str, enemies_hint: dict[str, str] | None = None
) -> State:
    """Reconstruct the live state from a client-supplied FEN.

    The white piece kind and star come from the server-stored answer (never
    trusted from the client); piece placement comes from the FEN so captures
    so far are reflected. Raises ValueError when the FEN does not describe
    exactly one matching white mover plus allowed black pieces (no kings).
    """
    kind = _norm_kind(white_kind, ALLOWED_WHITE_KINDS)
    tgt = _norm_square(target)
    if kind is None or tgt is None:
        raise ValueError("invalid_state")
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ValueError("invalid_fen") from exc
    white_sq: str | None = None
    enemies: list[tuple[str, str]] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        name = chess.square_name(sq)
        sym = piece.symbol()
        if piece.color == chess.WHITE:
            if sym != WHITE_LETTER[kind] or white_sq is not None:
                raise ValueError("invalid_fen")
            white_sq = name
        else:
            ekind = LETTER_TO_ENEMY.get(sym)
            if ekind is None:
                raise ValueError("invalid_fen")
            if enemies_hint is not None and enemies_hint.get(name, ekind) != ekind:
                raise ValueError("invalid_fen")
            enemies.append((name, ekind))
    if white_sq is None:
        raise ValueError("invalid_fen")
    enemies.sort()
    return State(white_kind=kind, white_square=white_sq, enemies=tuple(enemies), target=tgt)


# --- Exact shortest-path solver (BFS over complete states) ---

# Practical guard: with <= 5 enemies the reachable state space stays far
# below this; exceeding it means a degenerate position the generator must
# reject (documented in docs/exercises/07-pathfinding-obstacles.md).
MAX_VISITED = 30000


def solve(
    state: State, *, max_visited: int = MAX_VISITED
) -> dict[str, Any] | None:
    """BFS over complete board states. Returns the shortest solution or None.

    Every white move costs 1, so the first discovered goal state is
    optimal. Result: ``{"optimal_moves", "path", "captures", "visited"}``
    where ``path`` lists squares from start to star. ``None`` means no
    safe route exists (or the visited cap was hit).
    """
    if state.white_square == state.target:
        return {"optimal_moves": 0, "path": [state.white_square], "captures": 0, "visited": 1}
    visited: set[tuple] = {state.key()}
    # predecessor: state key -> (parent key, move dest, captured square|None)
    parent: dict[tuple, tuple[tuple, str, str | None]] = {}
    states: dict[tuple, State] = {state.key(): state}
    queue: deque[tuple] = deque([state.key()])
    while queue:
        key = queue.popleft()
        current = states[key]
        for dest, info in legal_transitions(current).items():
            nxt = apply_move(current, dest)
            # apply_move re-derives the same transition; it cannot fail here
            # because dest came from legal_transitions.
            assert nxt is not None
            nkey = nxt.key()
            if nkey in visited:
                continue
            visited.add(nkey)
            if len(visited) > max_visited:
                return None
            states[nkey] = nxt
            parent[nkey] = (key, dest, info["captured"])
            if nxt.white_square == nxt.target:
                # Reconstruct one optimal route by walking parent links
                # back to the start (each link stores the move that led
                # into its state).
                rev: list[str] = [dest]
                caps = 1 if info["captured"] else 0
                walk = key
                while walk != state.key():
                    prev_key, move_sq, cap_sq = parent[walk]
                    rev.append(move_sq)
                    if cap_sq:
                        caps += 1
                    walk = prev_key
                rev.reverse()
                path = [state.white_square] + rev
                return {
                    "optimal_moves": len(path) - 1,
                    "path": path,
                    "captures": caps,
                    "visited": len(visited),
                }
            queue.append(nkey)
    return None


def empty_board_distance(kind: str, start: str, target: str) -> int | None:
    """Shortest distance ignoring all enemies (generator quality baseline)."""
    base = State(white_kind=kind, white_square=start, enemies=(), target=target)
    found = solve(base)
    return found["optimal_moves"] if found else None
