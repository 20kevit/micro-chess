"""Heavier Side material evaluation: material only, never positional.

Piece values (king = 0, excluded from totals):

    Pawn = 1, Knight = 3, Bishop = 3, Rook = 5, Queen = 9, King = 0.

Difficulty constraint (every served puzzle must satisfy it):

    difference = abs(white - black)
    larger = max(white, black)
    eligible <=> larger == 0 OR difference / larger <= 0.10

No rounding before comparison: 30 vs 27 is accepted, 30 vs 26 rejected.
"""

from __future__ import annotations

import chess

PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# Uppercase piece-letter -> value (kings map to 0, kept for completeness).
LETTER_VALUES: dict[str, int] = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}

MAX_RELATIVE_DIFFERENCE = 0.10


def material_from_board(board: chess.Board) -> tuple[int, int]:
    """Total material for (white, black) from a python-chess board.

    Kings contribute 0 and are effectively excluded.
    """
    white = 0
    black = 0
    for square, piece in board.piece_map().items():
        _ = square
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            white += value
        else:
            black += value
    return white, black


def material_from_fen(fen: str) -> tuple[int, int]:
    """Total material for (white, black) from a FEN string.

    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    return material_from_board(board)


def classify(white: int, black: int) -> str:
    """Deterministic answer classifier: white > black -> WHITE etc."""
    if white > black:
        return "white"
    if black > white:
        return "black"
    return "equal"


def classify_fen(fen: str) -> str:
    """Classify a FEN directly (material only). Raises on invalid FEN."""
    white, black = material_from_fen(fen)
    return classify(white, black)


def is_material_difference_acceptable(white: int, black: int) -> bool:
    """10% difficulty gate: difference / larger <= 0.10 (0/0 accepted)."""
    larger = max(white, black)
    if larger == 0:
        return True
    return abs(white - black) / larger <= MAX_RELATIVE_DIFFERENCE
