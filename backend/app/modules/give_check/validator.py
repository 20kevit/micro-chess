"""Giving Check validator: find EVERY legal move that checks the enemy king.

A move is a correct answer iff:

1. it is a legal chess move from the current position, AND
2. it is made by a non-King piece (kings can never legally give check,
   because the two kings may not stand on mutually attacking squares), AND
3. after the move, the opponent's king is in check.

Tactical quality is irrelevant: any legal checking move counts, even a
terrible one. No engine evaluation is used — legality plus the resulting
check status (both from python-chess) is the whole rule. This naturally
covers pins, discovered checks, double checks (one move = one answer),
captures with check, promotions (each checking promotion choice is a
distinct answer) and en passant where legal.

Puzzle definition (stored in the puzzle row):
- FEN holds the position (starting position never has either king in
  check; the generator enforces this with bounded rejection sampling).
- position_json: {"fen": "..."} (visible to the frontend for rendering).
- answer_json: {"moves": ["e2e4", "g7g8q", ...]} (UCI strings, never
  exposed; submission validation compares against them).

Attempt model (sent by the client):
    {"moves": [{"from": "e2", "to": "e4"}, {"from": "g7", "to": "g8",
     "promotion": "q"}]}  (promotion optional; plain UCI strings like
     "e2e4" are also accepted)

Direction matters ("e2e4" != "e4e2"); duplicates are normalized away.
A promotion missing its piece letter (e.g. {"from": "g7", "to": "g8"})
does NOT match "g7g8q": each checking promotion is a distinct move.

Result rules (same set semantics as Exercises 1-4):
- CORRECT: every checking move selected and nothing else (for a
  zero-target position, submitting no arrows is CORRECT and earns +5).
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  arrow when nothing gives check).
"""

from __future__ import annotations

import re
from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "give-check"

_PROMOTIONS = frozenset({"q", "r", "b", "n"})
_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def normalize_move_uci(raw: Any) -> str | None:
    """Normalize one submitted/stored move to a canonical UCI string.

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


def either_king_in_check(fen: str) -> bool:
    """True when White's OR Black's king is currently attacked.

    python-chess ``is_check()`` only reports the side to move, so both
    kings are tested explicitly via ``is_attacked_by``. Raises ValueError
    on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    for color in (chess.WHITE, chess.BLACK):
        king = board.king(color)
        if king is not None and board.is_attacked_by(not color, king):
            return True
    return False


def checking_moves(fen: str) -> list[str]:
    """Every legal non-King move (UCI) that leaves the opponent in check.

    Raises ValueError on invalid FEN. King moves are excluded by rule:
    a king can never legally give check. Castling is therefore never an
    answer; en passant and promotions are included when they check.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    found: list[str] = []
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        board.push(move)
        try:
            if board.is_check():
                found.append(move.uci())
        finally:
            board.pop()
    return sorted(found)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_moves(puzzle_answer.get("moves", []) if isinstance(puzzle_answer, dict) else [])
    answer = attempt if isinstance(attempt, dict) else {}
    selected, malformed = split_moves(answer.get("moves", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted(selected - expected) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # Zero-target position: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
