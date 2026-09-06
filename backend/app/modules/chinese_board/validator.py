"""Chinese Board validator: reconstruct a memorized position piece by piece.

Puzzle definition (stored in the puzzle row, never exposed to clients):

- answer_json: {"fen": "..."} (server-only source of truth).
- position_json: {"fen": "...", "piece_count": N, "memorization_ms": M,
  "mode": "standard"} (visible board + authoritative study budget).

Attempt model (sent by client):

    {"pieces": [{"square": "e1", "piece": "K", "color": "white"}, ...]}

Only ``pieces`` is read; client-supplied score/count/FEN fields are ignored
— correctness is always recomputed from the stored FEN.

Matching algorithm (deterministic, no double-counting):

1. Exact ``(color, type, square)`` matches first → correct (+5 each).
2. Remaining originals vs remaining user pieces are paired by identical
   ``(color, type)`` on different squares → each pair is ONE wrong
   original piece (-2). A queen remembered on the wrong square is a
   single error, not a missing plus an extra.
3. Still-unmatched originals → missing (-2 each).
4. Still-unmatched user pieces → extra (-2 each).

Result rules: CORRECT iff the reconstruction equals the original exactly
(no wrong, no missing, no extra); otherwise WRONG. No PARTIAL — the
per-piece score already expresses partial progress. Malformed input
(invalid entries, two pieces on one square, missing/invalid FEN) fails
safely as WRONG and never crashes the API.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.modules.chinese_board import pieces as cb
from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "chinese-board"

_VALID_KINDS = set(cb.PIECE_LETTERS)
_VALID_COLORS = set(cb.COLORS)


def normalize_entry(raw: Any) -> tuple[str, str, str] | None:
    """Normalize one placement to (color, kind, square). None when malformed."""
    if not isinstance(raw, dict):
        return None
    square = normalize_square(raw.get("square"))
    piece = raw.get("piece")
    color = raw.get("color")
    if square is None or not isinstance(piece, str) or not isinstance(color, str):
        return None
    kind = piece.strip().upper()
    side = color.strip().lower()
    if kind not in _VALID_KINDS or side not in _VALID_COLORS:
        return None
    return side, kind, square


def _wrong_result(piece_count: int, memorization_ms: int) -> ValidationResult:
    """Fail-safe WRONG: every original piece counts as missing."""
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={
            "correct": [],
            "missed": [],
            "wrong": [],
            "missing": [],
            "extra": [],
            "correct_squares": [],
            "missed_squares": [],
            "wrong_squares": [],
            "piece_count": piece_count,
            "memorization_ms": memorization_ms,
        },
    )


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    fen = answer.get("fen")
    raw_pieces = attempt_map.get("pieces")

    if not isinstance(fen, str) or not isinstance(raw_pieces, list):
        return _wrong_result(0, 0)
    try:
        original = cb.extract_pieces(fen)
    except ValueError:
        return _wrong_result(0, 0)
    count = len(original)
    budget = count * cb.MEMORIZE_MS_PER_PIECE

    normalized: list[tuple[str, str, str]] = []
    seen_squares: set[str] = set()
    for entry in raw_pieces:
        item = normalize_entry(entry)
        if item is None:
            return _wrong_result(count, budget)
        if item[2] in seen_squares:
            # Two pieces on one square can never be a valid reconstruction.
            return _wrong_result(count, budget)
        seen_squares.add(item[2])
        normalized.append(item)

    original_keys = [(d["color"], d["type"], d["square"]) for d in original]

    # Step 1: exact (color, type, square) matches.
    original_rest = Counter(original_keys)
    user_rest = Counter(normalized)
    exact = sorted(original_rest & user_rest)
    original_rest.subtract(exact)
    user_rest.subtract(exact)
    original_rest = +original_rest
    user_rest = +user_rest

    # Step 2: same (color, type) on a wrong square → one wrong piece each.
    # Pair deterministically: sort both sides, match greedily per kind key.
    remaining_original = sorted(original_rest.elements())
    remaining_user = sorted(user_rest.elements())
    orig_by_kind: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    user_by_kind: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for key in remaining_original:
        orig_by_kind.setdefault((key[0], key[1]), []).append(key)
    for key in remaining_user:
        user_by_kind.setdefault((key[0], key[1]), []).append(key)
    wrong_pairs: list[tuple[tuple[str, str, str], tuple[str, str, str]]] = []
    leftover_original: list[tuple[str, str, str]] = []
    leftover_user: list[tuple[str, str, str]] = []
    for kind_key in sorted(set(orig_by_kind) | set(user_by_kind)):
        originals = orig_by_kind.get(kind_key, [])
        users = user_by_kind.get(kind_key, [])
        pairs = min(len(originals), len(users))
        for i in range(pairs):
            wrong_pairs.append((originals[i], users[i]))
        leftover_original.extend(originals[pairs:])
        leftover_user.extend(users[pairs:])

    correct = [cb.describe(c, k, s) for (c, k, s) in exact]
    wrong = [cb.describe(c, k, s) for (c, k, s), _ in wrong_pairs]
    missing = [cb.describe(c, k, s) for (c, k, s) in sorted(leftover_original)]
    extra = [cb.describe(c, k, s) for (c, k, s) in sorted(leftover_user)]

    if not wrong and not missing and not extra:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={
                "correct": correct,
                "missed": [],
                "wrong": [],
                "missing": [],
                "extra": [],
                "correct_squares": sorted(s for _, _, s in exact),
                "missed_squares": [],
                "wrong_squares": [],
                "piece_count": count,
                "memorization_ms": budget,
            },
        )
    # Square overlays for the result UI: user-board errors vs answer-board gaps.
    wrong_user_squares = sorted(user_sq for _, (_, _, user_sq) in wrong_pairs)
    extra_user_squares = sorted(s for _, _, s in leftover_user)
    missed_original_squares = sorted(s for _, _, s in leftover_original)
    wrong_original_squares = sorted(orig_sq for (_, _, orig_sq), _ in wrong_pairs)
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={
            "correct": correct,
            "missed": missing,
            "wrong": wrong + extra,
            "missing": missing,
            "extra": extra,
            "correct_squares": sorted(s for _, _, s in exact),
            "missed_squares": sorted(set(missed_original_squares + wrong_original_squares)),
            "wrong_squares": sorted(set(wrong_user_squares + extra_user_squares)),
            "piece_count": count,
            "memorization_ms": budget,
        },
    )
