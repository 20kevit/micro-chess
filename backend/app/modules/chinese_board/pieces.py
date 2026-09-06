"""Chinese Board shared piece helpers: extraction, counting, timing.

Pure functions over FEN strings. Only piece placement matters (piece type
+ color + square); side to move, castling rights, en passant, and clocks
are ignored — this is a piece-placement memory exercise.

Memorization rule: ``memorization_ms = piece_count * 400``. The count is
naturally bounded by chess itself (at most 32 pieces on a legal board, so
at most 12800 ms); no artificial difficulty filter is applied. Measured on
the real ``puzzles.db`` (5.3M rows, 2000-position sample): piece counts
span 4-32 with the bulk at 7-26 and a median near 18-19, i.e. roughly
1.6s-12.8s of study time. Every real position is servable as-is.
"""

from __future__ import annotations

import chess

# Memorization budget per piece (0.4 seconds, spec section 4).
MEMORIZE_MS_PER_PIECE = 400

# Canonical piece letters (uppercase) accepted in attempts.
PIECE_LETTERS = ("K", "Q", "R", "B", "N", "P")

# Canonical colors accepted in attempts.
COLORS = ("white", "black")


def _symbol_of(color: str, kind: str) -> str:
    """python-chess symbol: uppercase for white, lowercase for black."""
    return kind if color == "white" else kind.lower()


def extract_pieces(fen: str) -> list[dict[str, str]]:
    """Every piece on the board as ``{"color", "type", "square"}`` dicts.

    Raises ValueError on invalid FEN. Sorted by square for determinism.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    out: list[dict[str, str]] = []
    for square, piece in board.piece_map().items():
        color = "white" if piece.color == chess.WHITE else "black"
        kind = piece.symbol().upper()
        out.append({"color": color, "type": kind, "square": chess.square_name(square)})
    out.sort(key=lambda d: d["square"])
    return out


def piece_count(fen: str) -> int:
    """Total pieces on the board. Raises ValueError on invalid FEN."""
    return len(extract_pieces(fen))


def memorization_ms(fen: str) -> int:
    """Authoritative study budget: ``piece_count * 400`` ms.

    Raises ValueError on invalid FEN.
    """
    return piece_count(fen) * MEMORIZE_MS_PER_PIECE


def describe(color: str, kind: str, square: str) -> str:
    """Deterministic descriptor for one placed piece, e.g. ``white:Q@d4``."""
    return f"{color}:{kind}@{square}"
