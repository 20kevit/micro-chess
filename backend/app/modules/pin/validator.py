"""Pin validator: identify the three pieces forming a pin, in order.

A classical pin has an enemy Rook, Bishop or Queen as the pinning piece:

    pinner (enemy slider) -> pinned piece -> valuable piece behind it

The piece behind is the King (absolute pin) or a strictly more valuable
piece (relative pin, material values P=1 N=3 B=3 R=5 Q=9). An alignment
where the front piece is more valuable than the rear piece is a skewer,
NOT a pin, and is rejected.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "pin": ["e1", "e6", "e8"]}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position — never from a stored
  triplet and never from client data.

Attempt model (sent by client, order matters):
    {"squares": ["<pinner>", "<pinned>", "<behind>"]}

A submission is CORRECT only when the three squares exactly equal the
single pin triplet of the stored position, in [pinner, pinned, behind]
order. Positions are seeded with exactly one pin, so there is exactly one
intended answer. Anything else (wrong squares, wrong order, skewer order,
missing/extra squares) is WRONG.

Result rules: CORRECT or WRONG only (a triplet is atomic, never partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "pin"

# Material values for the relative-pin gate: the rear piece must be
# strictly more valuable than the pinned piece (king = absolute pin).
_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

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
    """All classical pins on the board, each as a dict with pinner, pinned,
    behind (square names, in answer order) and absolute (bool).

    Absolute = behind is the King. Relative = behind is strictly more
    valuable than the pinned piece. Skewers (equal/lower-value behind)
    are NOT pins and are excluded. Kings can never be the pinned piece.

    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    pins: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for middle in chess.SQUARES:
        piece = board.piece_at(middle)
        if piece is None or piece.piece_type == chess.KING:
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
                slider, behind_sq = first_piece, second
            elif second_piece.color != piece.color and first_piece.color == piece.color:
                slider, behind_sq = second_piece, first
            else:
                continue
            if slider.piece_type not in (chess.ROOK, chess.BISHOP, chess.QUEEN):
                continue
            if not _slider_attacks_along(slider, axis):
                continue
            behind = board.piece_at(behind_sq)
            if behind is None:
                continue
            if behind.piece_type == chess.KING:
                absolute = True
            elif _PIECE_VALUES.get(behind.piece_type, 0) > _PIECE_VALUES.get(piece.piece_type, 0):
                absolute = False
            else:
                # Equal or lower value behind: skewer, not a pin.
                continue
            slider_sq = first if slider is first_piece else second
            key = (
                chess.square_name(slider_sq),
                chess.square_name(middle),
                chess.square_name(behind_sq),
            )
            if key in seen:
                continue
            seen.add(key)
            pins.append(
                {
                    "pinner": key[0],
                    "pinned": key[1],
                    "behind": key[2],
                    "absolute": absolute,
                }
            )
    return sorted(pins, key=lambda p: (p["pinner"], p["pinned"], p["behind"]))


def _pin_triplet(pin: dict[str, Any]) -> list[str]:
    return [pin["pinner"], pin["pinned"], pin["behind"]]


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    attempt_map = attempt if isinstance(attempt, dict) else {}
    raw = attempt_map.get("squares", attempt_map.get("selected_squares"))

    if not isinstance(fen, str):
        submitted = [str(s) for s in raw] if isinstance(raw, list) else []
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": submitted},
        )
    try:
        pins = find_pins(fen)
    except ValueError:
        submitted = [str(s) for s in raw] if isinstance(raw, list) else []
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": submitted},
        )
    if not pins:
        # Broken puzzle (no pin on the board): nothing can be correct.
        submitted = [str(s) for s in raw] if isinstance(raw, list) else []
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": submitted},
        )
    triplets = [_pin_triplet(p) for p in pins]
    expected = triplets[0]

    squares: list[str] = []
    if isinstance(raw, list) and len(raw) == 3:
        normalized = [normalize_square(s) for s in raw]
        if all(s is not None for s in normalized):
            squares = [s for s in normalized if s is not None]

    if squares in triplets:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={"correct": squares, "missed": [], "wrong": []},
        )
    submitted = [str(s) for s in raw] if isinstance(raw, list) else []
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={"correct": [], "missed": expected, "wrong": submitted},
    )
