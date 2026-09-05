"""Persian verbal description of a chess position (blindfold support).

Generates a deterministic, human-readable Persian description from a FEN
so the user can reconstruct the position mentally without seeing a board:

    Side to move -> White pieces -> Black pieces

Within each color pieces are ordered King, Queen, Rooks, Bishops,
Knights, Pawns; within each type squares are sorted alphabetically.
Square names stay in algebraic form (a1..h8) and are never translated.

This module is also the future TTS boundary: an audio provider can call
``describe_position`` and feed the returned text to ``AudioPort.synthesize``
(see ``app.modules.audio.ports``) without any new puzzle plumbing.
"""

import chess

PIECE_FA: dict[int, str] = {
    chess.KING: "شاه",
    chess.QUEEN: "وزیر",
    chess.ROOK: "رخ",
    chess.BISHOP: "فیل",
    chess.KNIGHT: "اسب",
    chess.PAWN: "سرباز",
}

COLOR_FA: dict[bool, str] = {
    chess.WHITE: "سفید",
    chess.BLACK: "سیاه",
}

# Deterministic presentation order: King, Queen, Rooks, Bishops, Knights, Pawns.
_PRESENTATION_ORDER = (
    chess.KING,
    chess.QUEEN,
    chess.ROOK,
    chess.BISHOP,
    chess.KNIGHT,
    chess.PAWN,
)


def _join_fa(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "، ".join(items[:-1]) + " و " + items[-1]


def _pieces_sentence(color: bool, board: chess.Board) -> str:
    parts: list[str] = []
    for piece_type in _PRESENTATION_ORDER:
        squares = sorted(
            chess.square_name(sq)
            for sq in chess.SQUARES
            if (p := board.piece_at(sq)) is not None
            and p.color == color
            and p.piece_type == piece_type
        )
        for sq in squares:
            parts.append(f"{PIECE_FA[piece_type]} در {sq}")
    if not parts:
        return f"مهره‌های {COLOR_FA[color]}: هیچ."
    return f"مهره‌های {COLOR_FA[color]}: {_join_fa(parts)}."


def describe_position(fen: str) -> str:
    """Return the deterministic Persian description for a FEN.

    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    turn = f"نوبت {COLOR_FA[board.turn]} است."
    white = _pieces_sentence(chess.WHITE, board)
    black = _pieces_sentence(chess.BLACK, board)
    extra: list[str] = []
    if board.castling_xfen() != "-":
        extra.append("حق قلعه‌رفتن وجود دارد.")
    if board.ep_square is not None:
        extra.append(f"خانه آنپاسان: {chess.square_name(board.ep_square)}.")
    return " ".join([turn, white, black, *extra])


def side_to_move(fen: str) -> str:
    """Return 'white' or 'black' for a FEN. Raises ValueError on invalid FEN."""
    return "white" if chess.Board(fen).turn == chess.WHITE else "black"
