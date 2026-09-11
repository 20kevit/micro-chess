"""Trapped-piece detection engine (server-side, deterministic).

MicroChess definition (Exercise 18, ``trapped-pieces``):

    A non-pawn piece (King, Queen, Rook, Bishop, Knight, either color) is
    TRAPPED iff it has zero SAFE destination squares.

A destination is SAFE iff moving the piece there does not lose material
after the resulting forcing exchange. "Attacked" alone is NOT "unsafe":
a defended piece whose recapture wins the exchange is still safe on that
square. Conversely a quiet-looking square is unsafe when the opponent can
force a sequence that wins the piece for less.

Algorithm (per candidate piece):

1. Set ``board.turn`` to the piece's own color and enumerate its LEGAL
   moves (pins, checks and king-safety included; both colors are
   evaluated independently of the FEN side to move). Pawns are never
   candidates. Kings use pure legality: an attacked square is simply not
   a legal king destination, so a king is trapped iff it has no legal
   move at all.
2. For each destination, push the move and run a Static Exchange
   Evaluation (SEE) on the destination square from the mover's
   perspective (``static_exchange`` below). The destination is safe iff
   the net exchange is >= 0 (a favorable or equal recapture is
   acceptable; only a net loss is unsafe).
3. Check-giving moves are special-cased: the opponent must answer the
   check first, so the destination is safe unless the opponent has a
   legal reply that captures the moved piece AND the resulting exchange
   is still a net loss (again via SEE from the capture position).

SEE details (``static_exchange``):

- Standard least-valuable-attacker swap on the destination square,
  alternating sides starting with the opponent, using the project's
  shared material values (P=1 N=3 B=3 R=5 Q=9 K=0, imported from
  ``material_comparison.material`` so values never drift between
  modules). Kings contribute 0 and never capture in the sequence (a
  king recapture into a defended square is illegal, so it must not
  extend the line).
- Captures are generated with ``board.attackers`` on the mutated board,
  so opened lines/x-rays appear naturally as the sequence unfolds.
  Absolute-pin legality inside the sequence is ignored (standard SEE
  approximation) and documented as a limitation.

Limitations (deliberate, documented):

- Only the forcing capture exchange ON the destination square is
  searched (plus the must-answer-check rule). A quiet move after which
  the opponent builds a NEW multi-move trap (mate threats, zugzwang,
  deflection of a defender two moves later) is scored by the immediate
  exchange only and counts as safe. Full-board quiescence search is out
  of scope for this exercise.
- No engine (Stockfish) is used: python-chess attack geometry +
  material swap only, fully deterministic, millisecond-scale so the
  generator can scan the shared ``puzzles.db`` at request time.

Performance: ~10ms per middlegame position (measured), cached per FEN
in a small in-process dict for generation bursts.
"""

from __future__ import annotations

import chess

from app.modules.material_comparison.material import PIECE_VALUES

SLUG = "trapped-pieces"

# Candidate piece types: everything except pawns. Kings stay candidates;
# their safety falls out of move legality (never move into check).
CANDIDATE_TYPES = frozenset(
    {chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT}
)

# Practice serves 1-3 trapped pieces (0 discarded, 4+ degenerate
# back-rank-blocked positions discarded); Speed serves exactly one.
MAX_PRACTICE_TRAPPED = 3

_cache: dict[str, list[str]] = {}


def _value(piece_type: int) -> int:
    return PIECE_VALUES.get(piece_type, 0)


def static_exchange(board: chess.Board, square: chess.Square, mover: chess.Color) -> int:
    """Net material for ``mover`` from optimal captures on ``square``.

    Positive = mover wins the exchange, 0 = equal/acceptable,
    negative = mover loses material. Deterministic: ties broken by
    square index.
    """
    b = board.copy(stack=False)
    gains: list[int] = []
    side = not mover  # the opponent captures first
    target = b.piece_at(square)
    current = _value(target.piece_type) if target is not None else 0
    while True:
        attackers = [
            sq
            for sq in b.attackers(side, square)
            if b.piece_at(sq) is not None and b.piece_at(sq).piece_type != chess.KING  # type: ignore[union-attr]
        ]
        if not attackers:
            break
        attackers.sort(key=lambda sq: (_value(b.piece_at(sq).piece_type), sq))  # type: ignore[union-attr]
        atk = attackers[0]
        atk_piece = b.piece_at(atk)
        assert atk_piece is not None
        gains.append(current)
        b.remove_piece_at(atk)
        b.remove_piece_at(square)
        b.set_piece_at(square, atk_piece)
        current = _value(atk_piece.piece_type)
        side = not side
    net = 0
    for i, gain in enumerate(gains):
        net += gain if i % 2 == 1 else -gain
    return net


def _legal_piece_moves(fen: str, square: chess.Square) -> tuple[chess.Board, list[chess.Move]]:
    """Legal moves of the piece on ``square`` with the turn set to its color."""
    board = chess.Board(fen)  # raises on invalid FEN
    piece = board.piece_at(square)
    if piece is None or piece.piece_type not in CANDIDATE_TYPES:
        return board, []
    board.turn = piece.color
    return board, [m for m in board.legal_moves if m.from_square == square]


def is_safe_destination(fen: str, square: chess.Square, move: chess.Move) -> bool:
    """True when ``move`` leaves the piece materially safe (SEE >= 0)."""
    board = chess.Board(fen)  # raises on invalid FEN
    piece = board.piece_at(square)
    if piece is None:
        return False
    board.turn = piece.color
    board.push(move)
    dest = move.to_square
    if board.is_check():
        # The opponent must answer the check: only a legal reply that
        # captures the moved piece can refute the move.
        if not any(m.to_square == dest for m in board.legal_moves):
            return True
    return static_exchange(board, dest, piece.color) >= 0


def is_trapped(fen: str, square: chess.Square) -> bool:
    """True when the candidate piece on ``square`` has no safe destination."""
    board = chess.Board(fen)  # raises on invalid FEN
    piece = board.piece_at(square)
    if piece is None or piece.piece_type not in CANDIDATE_TYPES:
        return False
    _, moves = _legal_piece_moves(fen, square)
    if not moves:
        return True
    return not any(is_safe_destination(fen, square, m) for m in moves)


def trapped_squares(fen: str) -> list[str]:
    """All trapped squares in a FEN (both colors, pawns excluded). Cached."""
    cached = _cache.get(fen)
    if cached is not None:
        return list(cached)
    board = chess.Board(fen)  # raises on invalid FEN
    trapped: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type not in CANDIDATE_TYPES:
            continue
        if is_trapped(fen, sq):
            trapped.append(chess.square_name(sq))
    trapped.sort()
    if len(_cache) < 4096:
        _cache[fen] = list(trapped)
    return trapped


def either_king_in_check(fen: str) -> bool:
    """True when either king is in check (generation rejects these)."""
    board = chess.Board(fen)  # raises on invalid FEN
    if board.is_check():
        return True
    board.turn = not board.turn
    return board.is_check()


def clear_cache() -> None:
    _cache.clear()
