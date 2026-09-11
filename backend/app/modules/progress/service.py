"""Attempt submission: Puzzle -> Validation -> Score -> Rating -> Feedback.

Backend is authoritative. Frontend never decides correctness.
Practice attempts never affect rating (rating_delta stays None).
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.exercises import registry
from app.modules.feedback_engine.service import feedback_key_for
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.service import preview_rating_delta
from app.modules.rule_engine.base import AttemptMode, AttemptResult, ValidationResult

CLIENT_TERMINAL_RESULTS = {
    "timeout": AttemptResult.TIMEOUT,
    "skipped": AttemptResult.SKIPPED,
    "abandoned": AttemptResult.ABANDONED,
}


def _answer_squares(answer_json: dict) -> list[str]:
    squares = answer_json.get("squares", [])
    return sorted({s for s in squares if isinstance(s, str)})


def _duration_ms(started_at: datetime | None, now: datetime) -> int | None:
    if started_at is None:
        return None
    start = started_at
    if start.tzinfo is not None:
        start = start.replace(tzinfo=None)
    delta = (now.replace(tzinfo=None) - start).total_seconds() * 1000
    return max(0, int(delta))


def submit_attempt(
    db: Session,
    *,
    user_id: int | None,
    guest_session_id: int | None = None,
    puzzle_id: int,
    answer: dict,
    mode: AttemptMode,
    client_result: str | None = None,
    hints_used: list[str] | None = None,
    started_at: datetime | None = None,
) -> tuple[Attempt, str, dict]:
    puzzle: Puzzle | None = db.get(Puzzle, puzzle_id)
    if puzzle is None or not puzzle.is_published or puzzle.is_archived:
        raise ValueError("puzzle_not_available")

    used_hints = [h for h in (hints_used or []) if isinstance(h, str)]

    normalized_client = (client_result or "").lower()
    if normalized_client in CLIENT_TERMINAL_RESULTS:
        result = CLIENT_TERMINAL_RESULTS[normalized_client]
        feedback_key = feedback_key_for(result)
        selected = answer.get("selected_squares", [])
        selected_set = {s for s in selected if isinstance(s, str)}
        detail = {
            "correct": [],
            "missed": _answer_squares(puzzle.answer_json),
            "wrong": sorted(selected_set),
        }
        validation = ValidationResult(result=result, message_key=feedback_key, detail=detail)
    else:
        validation = registry.validate_answer(puzzle.exercise_slug, puzzle.answer_json, answer)
        result = validation.result
        feedback_key = validation.message_key or feedback_key_for(result)
        detail = dict(validation.detail)

    # Authoritative score: exercise-specific scorer when registered
    # (e.g. per-square scoring), else the shared result -> score default.
    # Never trusted from the client. May be negative; never clamped here.
    score = registry.score_for_answer(puzzle.exercise_slug, validation)
    rating_delta: float | None = None
    if mode == AttemptMode.RATED and user_id is not None and result in (
        AttemptResult.CORRECT,
        AttemptResult.PARTIAL,
        AttemptResult.WRONG,
    ):
        # Placeholder until Glicko-2 lands; records intent without real math.
        # hints_used and puzzle initial_rating are persisted so the future
        # engine can account for hint usage and puzzle difficulty.
        rating_delta = preview_rating_delta(score=score)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user_id is not None and guest_session_id is not None:
        raise ValueError("attempt_owner_conflict")
    attempt = Attempt(
        user_id=user_id,
        guest_session_id=guest_session_id,
        puzzle_id=puzzle.id,
        exercise_slug=puzzle.exercise_slug,
        mode=mode.value,
        result=result.value,
        answer_json=answer,
        score=score,
        rating_delta=rating_delta,
        started_at=started_at.replace(tzinfo=None) if started_at and started_at.tzinfo else started_at,
        duration_ms=_duration_ms(started_at, now),
        hints_used=used_hints,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt, feedback_key, detail
