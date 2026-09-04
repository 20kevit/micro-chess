"""Pin validator: play any legal move that creates a classical pin.

A classical pin has an enemy Rook, Bishop or Queen as the pinning piece:
enemy slider → pinned piece → valuable piece behind it. The piece behind
is the King (absolute pin) or a non-King piece (relative pin). Only pins
created by the submitted move count: pins already present before the move
are subtracted.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "example": {"from": "e2", "to": "e4"}}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position — never from a stored
  move list.

Attempt model (sent by client):
    {"from": "e2", "to": "e4", "promotion": "q"}  (promotion optional)

A submission is CORRECT when the move is legal under standard chess rules
and the resulting position contains at least one pin that did not exist
before the move. Any such move counts, so positions with several solutions
accept them all.

Result rules: CORRECT or WRONG only (a single move cannot be partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "pin"

_PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}

# The four axes, each as a pair of opposite unit steps (file delta, rank delta).
_AXES = (
    ((1, 0), (-1, 0)),
    ((0, 1), (0, -1)),
    ((1, 1), (-1, -1)),
    ((1, -1), (-1, 1)),
)


def _ray_first(board: chess.Board, start: chess.Square, step: tuple[int, int]) -> chess.Square | None:
    """First occupied square from start along step, or None off the board."""
    file = chess.square_file(start) + step[0]
    rank = chess.square_rank(start) + step[1]
    while 0 <= file < 8 and 0 <= rank < 8:
        square = chess.square(file, rank)
        if board.piece_at(square) is not None:
            return square
        file += step[0]
        rank += step[1]
    return None


def _slider_attacks_along(piece: chess.Piece, axis: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    """Whether a Rook/Bishop/Queen attacks along the given axis."""
    orthogonal = axis in (_AXES[0], _AXES[1])
    if piece.piece_type == chess.ROOK:
        return orthogonal
    if piece.piece_type == chess.BISHOP:
        return not orthogonal
    return piece.piece_type == chess.QUEEN


def find_pins(fen: str) -> list[dict[str, Any]]:
    """All classical pins on the board, each as a dict with pinned, behind,
    pinner (square names) and absolute (bool). Used by seed verification.

    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    pins: list[dict[str, Any]] = []
    for middle in chess.SQUARES:
        piece = board.piece_at(middle)
        if piece is None:
            continue
        for axis in _AXES:
            first = _ray_first(board, middle, axis[0])
            second = _ray_first(board, middle, axis[1])
            if first is None or second is None:
                continue
            first_piece = board.piece_at(first)
            second_piece = board.piece_at(second)
            if first_piece is None or second_piece is None:
                continue
            if first_piece.color != piece.color and second_piece.color == piece.color:
                slider, behind = first_piece, second_piece
            elif second_piece.color != piece.color and first_piece.color == piece.color:
                slider, behind = second_piece, first_piece
            else:
                continue
            if not _slider_attacks_along(slider, axis):
                continue
            pins.append(
                {
                    "pinned": chess.square_name(middle),
                    "behind": chess.square_name(second if slider is first_piece else first),
                    "pinner": chess.square_name(first if slider is first_piece else second),
                    "absolute": behind.piece_type == chess.KING,
                }
            )
    return sorted(pins, key=lambda p: (p["pinned"], p["behind"], p["pinner"]))


def _pin_key(pin: dict[str, Any]) -> tuple[str, str, str]:
    return (pin["pinned"], pin["behind"], pin["pinner"])


def creates_pin(fen: str, from_sq: str, to_sq: str, promotion: Any = None) -> bool:
    """True when from→to is legal and creates at least one new pin.

    Raises ValueError on invalid FEN or squares. An explicit promotion
    restricts to that choice; without one, any pinning promotion counts.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    origin = chess.parse_square(from_sq.strip().lower())
    dest = chess.parse_square(to_sq.strip().lower())
    before = {_pin_key(p) for p in find_pins(fen)}
    promo: chess.PieceType | None = None
    if promotion is not None:
        if not isinstance(promotion, str) or promotion.strip().lower() not in _PROMOTIONS:
            return False
        promo = _PROMOTIONS[promotion.strip().lower()]
    candidates = [
        m
        for m in board.legal_moves
        if m.from_square == origin and m.to_square == dest and (promo is None or m.promotion == promo)
    ]
    if not candidates:
        return False
    for move in candidates:
        board.push(move)
        try:
            after = {_pin_key(p) for p in find_pins(board.fen())}
            if after - before:
                return True
        finally:
            board.pop()
    return False


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    attempt_map = attempt if isinstance(attempt, dict) else {}
    origin = normalize_square(attempt_map.get("from"))
    dest = normalize_square(attempt_map.get("to"))
    promotion = attempt_map.get("promotion")

    squares = sorted(s for s in (origin, dest) if s is not None)
    # Malformed shape fails safely; unknown promotion letters fail below.
    if not isinstance(fen, str) or origin is None or dest is None:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": squares},
        )
    try:
        correct = creates_pin(fen, origin, dest, promotion)
    except ValueError:
        correct = False
    if correct:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": squares, "missed": [], "wrong": []},
        )
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={"correct": [], "missed": [], "wrong": squares},
    )
