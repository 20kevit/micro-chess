"""Memory Board validator: reconstruct a memorized position exactly.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "..."}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position — never from a stored
  piece list.

Attempt model (sent by client):
    {"pieces": [{"square": "e1", "piece": "K", "color": "white"}, ...],
     "turn": "white"}

A submission is CORRECT when the submitted placement matches the stored
placement exactly (same squares with same piece types and colors, no
extras, no missing pieces) and the submitted side to move matches. Square
and piece order do not matter. Hidden FEN metadata (castling rights,
en-passant square, clocks) is intentionally ignored: the task is the
visible position plus side to move.

Result rules: CORRECT or WRONG only. Malformed input fails safely as WRONG
and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "memory-board"

_PIECE_TYPES = {
    "K": chess.KING,
    "Q": chess.QUEEN,
    "R": chess.ROOK,
    "B": chess.BISHOP,
    "N": chess.KNIGHT,
    "P": chess.PAWN,
}

_COLORS = {"white": chess.WHITE, "black": chess.BLACK}


def normalize_entry(raw: Any) -> tuple[str, str] | None:
    """Normalize one placement to (square, symbol) with uppercase white /
    lowercase black python-chess symbols. Returns None when malformed."""
    if not isinstance(raw, dict):
        return None
    square = normalize_square(raw.get("square"))
    piece = raw.get("piece")
    color = raw.get("color")
    if square is None or not isinstance(piece, str) or not isinstance(color, str):
        return None
    kind = piece.strip().upper()
    side = color.strip().lower()
    if kind not in _PIECE_TYPES or side not in _COLORS:
        return None
    symbol = kind if side == "white" else kind.lower()
    return square, symbol


def normalize_turn(raw: Any) -> str | None:
    """Normalize the side to move. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    turn = raw.strip().lower()
    return turn if turn in _COLORS else None


def placement_map(fen: str) -> dict[str, str]:
    """Square → symbol map parsed from a FEN. Raises ValueError when invalid."""
    board = chess.Board(fen)  # raises on invalid FEN
    return {chess.square_name(sq): piece.symbol() for sq, piece in board.piece_map().items()}


def board_turn(fen: str) -> str:
    """Side to move parsed from a FEN ("white"/"black"). Raises ValueError."""
    board = chess.Board(fen)  # raises on invalid FEN
    return "white" if board.turn == chess.WHITE else "black"


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    attempt_map = attempt if isinstance(attempt, dict) else {}
    raw_pieces = attempt_map.get("pieces")
    turn = normalize_turn(attempt_map.get("turn"))

    if not isinstance(fen, str) or not isinstance(raw_pieces, list) or turn is None:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": []},
        )
    submitted: dict[str, str] = {}
    for entry in raw_pieces:
        normalized = normalize_entry(entry)
        if normalized is None:
            return ValidationResult(
                result=AttemptResult.WRONG,
                message_key="feedback.wrong",
                detail={"correct": [], "missed": [], "wrong": []},
            )
        square, symbol = normalized
        if square in submitted:
            # Two pieces on one square can never be a valid reconstruction.
            return ValidationResult(
                result=AttemptResult.WRONG,
                message_key="feedback.wrong",
                detail={"correct": [], "missed": [], "wrong": [square]},
            )
        submitted[square] = symbol
    try:
        expected = placement_map(fen)
        expected_turn = board_turn(fen)
    except ValueError:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": []},
        )
    if submitted == expected and turn == expected_turn:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": sorted(expected), "missed": [], "wrong": []},
        )
    correct = sorted(sq for sq, symbol in submitted.items() if expected.get(sq) == symbol)
    missed = sorted(sq for sq in expected if sq not in submitted or submitted[sq] != expected[sq])
    wrong = sorted(sq for sq in submitted if expected.get(sq) != submitted[sq])
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={"correct": correct, "missed": missed, "wrong": wrong},
    )
