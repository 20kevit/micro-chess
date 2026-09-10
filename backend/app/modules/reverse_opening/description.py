"""Short educational description for a reconstruction puzzle.

Keeps opening context generic: the task is rebuilding moves, never naming
the opening, so the text must not reveal the sequence.
"""

import chess


def describe_opening(fen: str, opening_fa: str) -> str:
    """One Persian paragraph: context + task. Raises ValueError if invalid."""
    board = chess.Board(fen)  # raises on invalid FEN
    mover = "سفید" if board.turn == chess.WHITE else "سیاه"
    return (
        f"این موقعیت مربوط به ابتدای یک بازی شطرنج است ({opening_fa}). "
        f"نوبت حرکت با {mover} است. "
        "حرکت‌هایی را که از ابتدای بازی باعث رسیدن به این وضعیت شده‌اند بازسازی کن."
    )
