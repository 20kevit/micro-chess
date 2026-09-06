"""Balance Scale validator: match the left pan's material value exactly.

New spec (Exercise 10, ترازو): the left pan holds 4–10 black pieces with
total value X. The user adds unlimited white pieces (pawn/knight/bishop/
rook/queen, max 10 on the pan) until both sides are exactly equal. ANY
exact combination solves the puzzle; fewer pieces score higher (see
``scoring.py``). No chess rules, no board, no kings — only material totals.

Puzzle definition (stored in the puzzle row, server-side only):
- answer_json: {"left": [...], "target": int, "optimal_count": int}
- position_json: {"left": [...]} (visible: the black target pieces only;
  the optimal count is NEVER exposed).

Attempt model (sent by client):
    {"pieces": ["q", "r", "p", ...]}

Server authority: the target and optimal count are ALWAYS recomputed
from the stored left pieces. Client-supplied score/optimal_count/
target_value fields are ignored.

Result rules: CORRECT iff every submitted piece is valid, at most 10
pieces were submitted, and the submitted total equals the stored target.
Anything else (under/over target, invalid piece, >10 pieces, malformed
input) is WRONG and never crashes the API.

Legacy rows (bank/right subset-sum shape from the earlier prototype) are
still graded by their original rule so existing databases keep working;
all newly generated puzzles use the left-target shape.
"""

from typing import Any

from app.modules.balance_scale import solver
from app.modules.balance_scale.solver import MAX_PIECES
from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "balance-scale"

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}


def normalize_piece(raw: Any) -> str | None:
    """Uppercase/validate a single piece id. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    piece = raw.strip().upper()
    return piece if piece in VALUES else None


def split_pieces(raw: Any) -> tuple[list[str], list[str]]:
    """Split raw input into (valid pieces, malformed entries).

    Malformed entries are returned as strings so callers can fail safely
    without crashing.
    """
    items = raw if isinstance(raw, list) else []
    valid: list[str] = []
    malformed: list[str] = []
    for entry in items:
        piece = normalize_piece(entry)
        if piece is None:
            malformed.append(str(entry))
        else:
            valid.append(piece)
    return valid, malformed


def total_value(pieces: list[str]) -> int:
    """Total material value. Caller must pass normalized pieces only."""
    return sum(VALUES[p] for p in pieces)


def counts(pieces: list[str]) -> dict[str, int]:
    """Multiset counts, so duplicate pieces are handled correctly."""
    result: dict[str, int] = {}
    for piece in pieces:
        result[piece] = result.get(piece, 0) + 1
    return result


def _wrong(
    submitted_value: int,
    target_value: int,
    used: int,
    optimal: int | None,
    submitted: list[str],
    malformed: list[str],
) -> ValidationResult:
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={
            "correct": [],
            "missed": [],
            "wrong": submitted + malformed,
            "submitted_value": submitted_value,
            "target_value": target_value,
            "used_count": used,
            "optimal_count": optimal,
        },
    )


def _validate_legacy(
    puzzle_answer: dict[str, Any], attempt: dict[str, Any]
) -> ValidationResult:
    """Original bank/right subset-sum rule (pre-Exercise-10 prototype)."""
    bank, bank_bad = split_pieces(puzzle_answer.get("bank"))
    right, right_bad = split_pieces(puzzle_answer.get("right"))
    submitted, malformed = split_pieces(attempt.get("pieces") if isinstance(attempt, dict) else None)

    target_value = total_value(right)
    submitted_value = total_value(submitted)
    detail: dict[str, Any] = {
        "correct": [],
        "missed": [],
        "wrong": submitted + malformed,
        "submitted_value": submitted_value,
        "target_value": target_value,
    }
    if bank_bad or right_bad or malformed:
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    available = counts(bank)
    for piece, needed in counts(submitted).items():
        if available.get(piece, 0) < needed:
            return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
    if submitted_value == target_value:
        detail["correct"] = submitted
        detail["wrong"] = []
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct", detail=detail)
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    # Legacy rows have no "left" key; grade them by the original rule.
    if "left" not in answer and ("bank" in answer or "right" in answer):
        return _validate_legacy(answer, attempt)

    left, left_bad = split_pieces(answer.get("left"))
    submitted, malformed = split_pieces(attempt.get("pieces") if isinstance(attempt, dict) else None)

    target_value = total_value(left)
    submitted_value = total_value(submitted)
    optimal = solver.optimal_count(target_value)
    used = len(submitted)

    if left_bad or not left or target_value <= 0 or optimal is None:
        return _wrong(submitted_value, target_value, used, optimal, submitted, malformed)
    if malformed:
        return _wrong(submitted_value, target_value, used, optimal, submitted, malformed)
    if used > MAX_PIECES:
        return _wrong(submitted_value, target_value, used, optimal, submitted, malformed)
    if submitted_value != target_value:
        return _wrong(submitted_value, target_value, used, optimal, submitted, malformed)

    return ValidationResult(
        result=AttemptResult.CORRECT,
        message_key="feedback.correct",
        detail={
            "correct": submitted,
            "missed": [],
            "wrong": [],
            "submitted_value": submitted_value,
            "target_value": target_value,
            "used_count": used,
            "optimal_count": optimal,
        },
    )
