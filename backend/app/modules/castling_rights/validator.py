"""Castling Rights validator: select every currently legal castling option.

The four stable option identifiers are white_kingside, white_queenside,
black_kingside and black_queenside. Legality always comes from python-chess
move generation: for each color the candidate castling UCI move must be a
member of that color's legal moves (checked on a turn-flipped board copy,
since `legal_moves` only covers the side to move). This covers rights flags,
king/rook presence, empty paths (including b1/b8) and king safety
(in check, transit and destination squares) without a parallel engine.

Puzzle definition (stored in the puzzle row):
- FEN holds the position.
- position_json: {"fen": "...", "mode": "standard"} (visible to frontend).
- answer_json: {"options": [...]} (never exposed; submission validation
  compares against it).

Attempt model (sent by client):
    {"options": ["white_kingside", "black_queenside"]}

Result rules:
- CORRECT: every legal option selected and nothing else. When no castling
  is legal, submitting an empty selection is CORRECT.
- PARTIAL: at least one correct selection, but missed and/or wrong ones exist.
- WRONG: no correct selections (includes malformed-only answers, and any
  selection when nothing is legal).
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "castling-rights"

OPTIONS = ("white_kingside", "white_queenside", "black_kingside", "black_queenside")

# Candidate king move and side to move for each option. Piece presence is
# checked separately so stale FEN flags fail safely (see _pieces_present).
_CANDIDATES: dict[str, tuple[bool, str]] = {
    "white_kingside": (chess.WHITE, "e1g1"),
    "white_queenside": (chess.WHITE, "e1c1"),
    "black_kingside": (chess.BLACK, "e8g8"),
    "black_queenside": (chess.BLACK, "e8c8"),
}


def _pieces_present(board: chess.Board, color: chess.Color, kingside: bool) -> bool:
    if color == chess.WHITE:
        king_from, rook_from = "e1", "h1" if kingside else "a1"
    else:
        king_from, rook_from = "e8", "h8" if kingside else "a8"
    king_piece = board.piece_at(chess.parse_square(king_from))
    rook_piece = board.piece_at(chess.parse_square(rook_from))
    return (
        king_piece is not None
        and king_piece.piece_type == chess.KING
        and king_piece.color == color
        and rook_piece is not None
        and rook_piece.piece_type == chess.ROOK
        and rook_piece.color == color
    )


def legal_castling_options(fen: str) -> list[str]:
    """Compute legal castling options from a FEN (used by seed + tests).

    A stale rights flag with a missing king or rook yields no option instead
    of an error. Submission validation compares against the stored answer
    and never recomputes from FEN or trusts client-provided option lists.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    legal: list[str] = []
    for option in OPTIONS:
        color, uci = _CANDIDATES[option]
        kingside = option.endswith("kingside")
        if not _pieces_present(board, color, kingside):
            continue
        probe = board.copy()
        probe.turn = color
        if chess.Move.from_uci(uci) in probe.legal_moves:
            legal.append(option)
    return sorted(legal)


def normalize_option(raw: Any) -> str | None:
    """Lowercase/validate a single option id. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    option = raw.strip().lower()
    return option if option in OPTIONS else None


def split_options(raw: Any) -> tuple[set[str], list[str]]:
    """Split raw input into (valid options, malformed entries).

    Malformed entries are returned as strings so callers can count them
    as incorrect selections without crashing.
    """
    items = raw if isinstance(raw, list) else []
    valid: set[str] = set()
    malformed: list[str] = []
    for entry in items:
        option = normalize_option(entry)
        if option is None:
            malformed.append(str(entry))
        else:
            valid.add(option)
    return valid, malformed


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    expected, _ = split_options(puzzle_answer.get("options", []))
    selected, malformed = split_options(attempt.get("options", []))

    correct = sorted(selected & expected)
    missed = sorted(expected - selected)
    wrong = sorted((selected - expected)) + sorted(malformed)

    detail = {"correct": correct, "missed": missed, "wrong": wrong}
    if not expected:
        # No castling is legal: only an empty submission is correct.
        if not selected and not malformed:
            return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not correct:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if not missed and not wrong:
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.PARTIAL, message_key="feedback.partial", detail=detail)
