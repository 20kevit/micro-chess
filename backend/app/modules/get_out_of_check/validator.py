"""Get Out of Check validator: find EVERY legal move that escapes the check.

Puzzle definition (stored in the puzzle row, never exposed to clients):
- answer_json: {"fen": "..."} (the FEN is the single source of truth; the
  complete answer set is derived from the position on every submission,
  never from a stored move list).
- position_json: {"fen": "..."} (visible to the frontend for rendering).
- Every puzzle starts with the side to move in check (White in generated
  puzzles; the validator itself is generic over ``board.turn``).

A move is a correct answer iff:

1. the side to move starts in check, AND
2. it is a legal chess move for the side to move from the current
   position (king safety enforced by python-chess, never pseudo-legal
   moves), AND
3. after the move, the moving side's own king is no longer in check
   (tested via ``is_attacked_by`` on the mover's king: ``is_check()``
   would test the opponent instead).

This single rule naturally covers the three conceptual mechanisms
(capture the checker, block the checking line, move the king) and the
double-check rule (only king moves can escape a genuine double check:
any non-king move leaves the second checker attacking). One distinct
chess move is one answer, regardless of how many mechanisms it uses.

Attempt model (sent by the client):
    {"moves": [{"from": "e1", "to": "d1"}, {"from": "g7", "to": "g8",
     "promotion": "q"}]}  (promotion optional; plain UCI strings like
     "e1d1" are also accepted; a legacy single-move {"from","to"} shape
     is accepted as one move)

Direction matters ("e1d1" != "d1e1"); duplicates are normalized away.
A promotion missing its piece letter (e.g. {"from": "g7", "to": "g8"})
does NOT match "g7g8q": each escaping promotion is a distinct move.

Result rules (same set semantics as Exercises 1-5):
- CORRECT: every escaping move selected and nothing else (order free).
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers).
- Positions not starting in check are invalid puzzles: every submission
  is WRONG (there is no zero-target bonus in this exercise; a valid
  puzzle always has at least one escape).
"""

from __future__ import annotations

import re
from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "get-out-of-check"

_PROMOTIONS = frozenset({"q", "r", "b", "n"})
_PROMOTION_TYPES = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}
_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def normalize_move_uci(raw: Any) -> str | None:
    """Normalize one submitted move to a canonical UCI string.

    Accepts {"from", "to", "promotion"?} dicts and plain UCI strings.
    Returns None when malformed (unknown squares, bad promotion letter,
    wrong shape). Malformed entries count as wrong, never crash.
    """
    if isinstance(raw, str):
        uci = raw.strip().lower()
        return uci if _UCI_RE.match(uci) else None
    if isinstance(raw, dict):
        origin = normalize_square(raw.get("from"))
        dest = normalize_square(raw.get("to"))
        if origin is None or dest is None:
            return None
        promotion = raw.get("promotion")
        if promotion is None:
            return f"{origin}{dest}"
        if not isinstance(promotion, str):
            return None
        promo = promotion.strip().lower()
        if promo in ("", "none"):
            return f"{origin}{dest}"
        if promo not in _PROMOTIONS:
            return None
        return f"{origin}{dest}{promo}"
    return None


def split_moves(raw: Any) -> tuple[set[str], list[str]]:
    """Split raw input into (valid UCI set, malformed entries)."""
    items = raw if isinstance(raw, list) else []
    valid: set[str] = set()
    malformed: list[str] = []
    for entry in items:
        uci = normalize_move_uci(entry)
        if uci is None:
            malformed.append(str(entry))
        else:
            valid.add(uci)
    return valid, malformed


def escaping_moves(fen: str) -> list[str]:
    """All legal check-escaping moves in UCI form (authoritative answer set).

    Raises ValueError on invalid FEN. Returns [] when the side to move
    is not in check (invalid puzzle for this exercise).
    """
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
        if not isinstance(promotion, str) or promotion.strip().lower() not in _PROMOTION_TYPES:
            return False
        promo = _PROMOTION_TYPES[promotion.strip().lower()]
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


def _selected_moves(answer: dict[str, Any]) -> tuple[set[str], list[str]]:
    """Extract the client's selected UCI set (+ malformed entries).

    Primary shape is {"moves": [...]}; a legacy single-move
    {"from","to","promotion"?} shape is accepted as exactly one move so
    older clients degrade gracefully instead of crashing.
    """
    selected, malformed = split_moves(answer.get("moves", []))
    if "moves" not in answer and (answer.get("from") is not None or answer.get("to") is not None):
        uci = normalize_move_uci(answer)
        if uci is None:
            malformed.append(str(answer))
        else:
            selected.add(uci)
    return selected, malformed


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    answer = attempt if isinstance(attempt, dict) else {}
    selected, malformed = _selected_moves(answer)

    try:
        expected = set(escaping_moves(fen)) if isinstance(fen, str) else set()
        fen_ok = isinstance(fen, str) and chess.Board(fen).is_check()
    except ValueError:
        expected = set()
        fen_ok = False

    if not fen_ok:
        # Invalid puzzle (not starting in check): nothing can be correct.
        # There is no zero-target bonus here; a valid puzzle always has
        # at least one escape, so even an empty submission is WRONG.
        wrong = sorted(selected) + sorted(malformed)
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": wrong},
        )

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted(selected - expected) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
