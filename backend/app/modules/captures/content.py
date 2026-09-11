"""Captures content invariants for Phase 07 validation.

Exercise-specific rules stay in the exercise domain: this hook
recomputes the authoritative capture set from the position and
requires the stored answer to match it exactly (solution legality).
Registered on import; core flow never branches on the exercise slug.
"""

from typing import Any

from app.modules.captures.validator import IGNORE_ENEMY_ATTACKS, SLUG, capturable_squares
from app.modules.puzzles.validation import register_content_validator


def check_captures_content(fields: dict[str, Any]) -> list[dict[str, Any]]:
    answer = fields.get("answer_json") or {}
    position = fields.get("position_json") or {}
    fen = fields.get("fen")
    squares = answer.get("squares")
    if not isinstance(squares, list):
        return [{"code": "answer_shape", "detail": "captures answer requires a squares list"}]
    if not fen:
        return [{"code": "fen_missing", "detail": "captures content requires a board position"}]
    from_sq = answer.get("from") or position.get("from")
    if not from_sq:
        return [{"code": "from_missing", "detail": "captures content requires the hunter square"}]
    profile = answer.get("profile") or position.get("profile") or IGNORE_ENEMY_ATTACKS
    try:
        expected = capturable_squares(fen, from_sq, profile)
    except ValueError as exc:
        return [{"code": "solution_illegal", "detail": f"capture set cannot be computed: {exc}"}]
    if sorted(str(s) for s in squares) != sorted(expected):
        return [
            {
                "code": "solution_mismatch",
                "detail": "stored answer does not match the legal capture set",
            }
        ]
    return []


register_content_validator(SLUG, check_captures_content)
