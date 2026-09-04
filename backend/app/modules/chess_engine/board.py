"""Minimal standard-chess helpers backed by python-chess.

Do NOT put exercise-specific rules here. Those belong in the
exercise's own validator (see exercises/registry + rule_engine/base).
"""

import chess


def parse_board(fen: str) -> chess.Board:
    return chess.Board(fen)


def legal_moves_uci(fen: str) -> list[str]:
    return [m.uci() for m in parse_board(fen).legal_moves]


def is_legal_uci(fen: str, uci: str) -> bool:
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return False
    return move in parse_board(fen).legal_moves


def piece_at(fen: str, square: str) -> str | None:
    """Return symbol like 'P'/'k' or None. Square like 'e4'."""
    try:
        sq = chess.parse_square(square.lower())
    except ValueError:
        return None
    piece = parse_board(fen).piece_at(sq)
    return piece.symbol() if piece else None
