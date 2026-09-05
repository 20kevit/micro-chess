"""Short Persian description of a square-rule position.

States only what stands where and whose move it is. It never mentions
the square geometry or the verdict, so it cannot leak the answer.
"""

import chess


def describe_position(fen: str) -> str:
    """One Persian paragraph for a FEN. Raises ValueError if invalid."""
    board = chess.Board(fen)  # raises on invalid FEN
    pawns = [
        sq
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None and p.piece_type == chess.PAWN
    ]
    if not pawns:
        raise ValueError("no_pawn")
    pawn = board.piece_at(pawns[0])
    color = "سفید" if pawn.color == chess.WHITE else "سیاه"
    kings = sorted(
        chess.square_name(sq)
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None and p.piece_type == chess.KING
    )
    mover = "سفید" if board.turn == chess.WHITE else "سیاه"
    return (
        f"پیاده {color} در {chess.square_name(pawns[0])} است. "
        f"شاه‌ها در {', '.join(kings)} هستند. "
        f"نوبت حرکت با {mover} است."
    )
