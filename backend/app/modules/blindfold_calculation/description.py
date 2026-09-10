"""Persian verbal description of a chess position (blindfold support).

Generates a deterministic, structured Persian description from a FEN so
the user can reconstruct the position mentally without seeing a board::

    موقعیت مهره‌ها

    سفید
    شاه: e4
    ...

    سیاه
    شاه: e8
    ...

    نوبت: سفید

Within each color pieces are ordered King, Queen, Rook, Bishop, Knight,
Pawn; within each type squares are listed in deterministic chessboard
order (file a..h, then rank 1..8). Empty piece types are omitted.
Square names stay in algebraic form (a1..h8) and are never translated.

Castling rights and the en-passant square travel in the FEN; when they
are meaningful the description says so explicitly, so no position is
impossible to reconstruct:

- any castling flag  -> "قلعه: ..." line naming the exact rights,
- an en-passant square -> "آنپاسان: ..." line.

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
    chess.PAWN: "پیاده",
}

COLOR_FA: dict[bool, str] = {
    chess.WHITE: "سفید",
    chess.BLACK: "سیاه",
}

# Deterministic presentation order: King, Queen, Rook, Bishop, Knight, Pawn.
_PRESENTATION_ORDER = (
    chess.KING,
    chess.QUEEN,
    chess.ROOK,
    chess.BISHOP,
    chess.KNIGHT,
    chess.PAWN,
)


def piece_count(fen: str) -> int:
    """Number of pieces on the board for a FEN. Raises ValueError if invalid."""
    board = chess.Board(fen)  # raises on invalid FEN
    return sum(1 for sq in chess.SQUARES if board.piece_at(sq) is not None)


def _squares_for(board: chess.Board, color: bool, piece_type: int) -> list[str]:
    """Algebraic squares for one color+type in chessboard order (file, rank)."""
    found = [
        sq
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None
        and p.color == color
        and p.piece_type == piece_type
    ]
    found.sort(key=lambda sq: (chess.square_file(sq), chess.square_rank(sq)))
    return [chess.square_name(sq) for sq in found]


def _color_section(board: chess.Board, color: bool) -> list[str]:
    """Lines for one color: header + one line per present piece type."""
    lines = [COLOR_FA[color]]
    for piece_type in _PRESENTATION_ORDER:
        squares = _squares_for(board, color, piece_type)
        if squares:
            lines.append(f"{PIECE_FA[piece_type]}: {'، '.join(squares)}")
    return lines


def _special_lines(board: chess.Board) -> list[str]:
    """Castling/en-passant lines so the position stays reconstructible."""
    lines: list[str] = []
    rights: list[str] = []
    if board.has_kingside_castling_rights(chess.WHITE):
        rights.append("سفید شاه‌طرف")
    if board.has_queenside_castling_rights(chess.WHITE):
        rights.append("سفید وزیرطرف")
    if board.has_kingside_castling_rights(chess.BLACK):
        rights.append("سیاه شاه‌طرف")
    if board.has_queenside_castling_rights(chess.BLACK):
        rights.append("سیاه وزیرطرف")
    if rights:
        lines.append(f"قلعه: {'، '.join(rights)}")
    if board.ep_square is not None:
        lines.append(f"آنپاسان: {chess.square_name(board.ep_square)}")
    return lines


def describe_position(fen: str) -> str:
    """Return the deterministic structured Persian description for a FEN.

    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    lines = ["موقعیت مهره‌ها", ""]
    lines.extend(_color_section(board, chess.WHITE))
    lines.append("")
    lines.extend(_color_section(board, chess.BLACK))
    lines.append("")
    lines.append(f"نوبت: {COLOR_FA[board.turn]}")
    lines.extend(_special_lines(board))
    return "\n".join(lines)


def side_to_move(fen: str) -> str:
    """Return 'white' or 'black' for a FEN. Raises ValueError on invalid FEN."""
    return "white" if chess.Board(fen).turn == chess.WHITE else "black"
