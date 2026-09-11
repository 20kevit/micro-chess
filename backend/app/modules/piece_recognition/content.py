"""Piece Recognition content invariants for Phase 07 validation.

Exercise-specific rules stay in the exercise domain: this hook
recomputes the authoritative target squares from the position and
requires the stored answer to match (solution legality).
Registered on import; core flow never branches on the exercise slug.
"""

from typing import Any

from app.modules.piece_recognition.validator import SLUG, TARGETS, squares_for_target
from app.modules.puzzles.validation import register_content_validator


def check_piece_recognition_content(fields: dict[str, Any]) -> list[dict[str, Any]]:
    answer = fields.get("answer_json") or {}
    position = fields.get("position_json") or {}
    fen = fields.get("fen")
    squares = answer.get("squares")
    if not isinstance(squares, list):
        return [{"code": "answer_shape", "detail": "piece-recognition answer requires a squares list"}]
    target = answer.get("target") or position.get("target")
    if target is None:
        return [{"code": "target_missing", "detail": "piece-recognition content requires a target"}]
    spec = TARGETS.get(target)
    if spec is None:
        return [{"code": "unknown_target", "detail": "piece-recognition target is not supported"}]
    if not fen:
        return [{"code": "fen_missing", "detail": "piece-recognition content requires a board position"}]
    try:
        expected = squares_for_target(fen, spec)
    except ValueError as exc:
        return [{"code": "solution_illegal", "detail": f"target squares cannot be computed: {exc}"}]
    if sorted(str(s) for s in squares) != sorted(expected):
        return [
            {
                "code": "solution_mismatch",
                "detail": "stored answer does not match the position targets",
            }
        ]
    return []


register_content_validator(SLUG, check_piece_recognition_content)
