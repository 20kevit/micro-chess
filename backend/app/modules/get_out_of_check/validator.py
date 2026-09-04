"""Get Out of Check validator: play any legal move that escapes the check.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "...", "example": {"from": "e1", "to": "d1"}}.
  The FEN must live here because validators only receive answer_json, and
  correctness is always recomputed from the position — never from a stored
  move list. Every puzzle starts with the side to move in check.

Attempt model (sent by client):
    {"from": "e1", "to": "d1", "promotion": "q"}  (promotion optional)

A submission is CORRECT when the side to move starts in check, the move is
legal under standard chess rules (python-chess: king moves, captures,
blocks and pins included) and the moving side's own king is no longer in
check afterwards. Any legal escaping move counts, so positions with several
solutions accept them all. Note the asymmetry with Give Check: after the
push we test the MOVER's king safety via is_attacked_by (is_check() would
test the opponent instead).

Result rules: CORRECT or WRONG only (a single move cannot be partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "get-out-of-check"

_PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}


def escaping_moves(fen: str) -> list[str]:
    """All legal check-escaping moves in UCI form (used by seed verification + tests)."""
    board = chess.Board(fen)  # raises on invalid FEN
    if not board.is_check():
        return []
    mover = board.turn
    found: list[str] = []
    for move in board.legal_moves:
        board.push(move)
        try:
            king = board.king(mover)
            if king is not None and not board.is_attacked_by(not mover, king):
                found.append(move.uci())
        finally:
            board.pop()
    return sorted(found)


def is_escaping_move(fen: str, from_sq: str, to_sq: str, promotion: Any = None) -> bool:
    """True when the side to move starts in check and from→to is a legal
    move after which its own king is safe.

    Raises ValueError on invalid FEN or squares. An explicit promotion
    restricts to that choice; without one, any escaping promotion counts.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    if not board.is_check():
        return False
    mover = board.turn
    origin = chess.parse_square(from_sq.strip().lower())
    dest = chess.parse_square(to_sq.strip().lower())
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
            king = board.king(mover)
            if king is not None and not board.is_attacked_by(not mover, king):
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
        correct = is_escaping_move(fen, origin, dest, promotion)
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
