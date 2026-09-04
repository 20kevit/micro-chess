"""Attempt submission: Puzzle -> Validation -> Score -> Rating -> Feedback.

Backend is authoritative. Frontend never decides correctness.
Practice attempts never affect rating (rating_delta stays None).
"""

from sqlalchemy.orm import Session

from app.modules.exercises import registry
from app.modules.feedback_engine.service import feedback_key_for
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.service import preview_rating_delta
from app.modules.rule_engine.base import AttemptMode, AttemptResult
from app.modules.scoring_engine.service import score_for

CLIENT_TERMINAL_RESULTS = {
    "timeout": AttemptResult.TIMEOUT,
    "skipped": AttemptResult.SKIPPED,
    "abandoned": AttemptResult.ABANDONED,
}


def submit_attempt(
    db: Session,
    *,
    user_id: int | None,
    puzzle_id: int,
    answer: dict,
    mode: AttemptMode,
    client_result: str | None = None,
) -> tuple[Attempt, str]:
    puzzle: Puzzle | None = db.get(Puzzle, puzzle_id)
    if puzzle is None or not puzzle.is_published or puzzle.is_archived:
        raise ValueError("puzzle_not_available")

    normalized_client = (client_result or "").lower()
    if normalized_client in CLIENT_TERMINAL_RESULTS:
        result = CLIENT_TERMINAL_RESULTS[normalized_client]
        feedback_key = feedback_key_for(result)
    else:
        validation = registry.validate_answer(puzzle.exercise_slug, puzzle.answer_json, answer)
        result = validation.result
        feedback_key = validation.message_key or feedback_key_for(result)

    score = score_for(result)
    rating_delta: float | None = None
    if mode == AttemptMode.RATED and user_id is not None and result in (
        AttemptResult.CORRECT,
        AttemptResult.PARTIAL,
        AttemptResult.WRONG,
    ):
        # Placeholder until Glicko-2 lands; records intent without real math.
        rating_delta = preview_rating_delta(score=score)

    attempt = Attempt(
        user_id=user_id,
        puzzle_id=puzzle.id,
        exercise_slug=puzzle.exercise_slug,
        mode=mode.value,
        result=result.value,
        answer_json=answer,
        score=score,
        rating_delta=rating_delta,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt, feedback_key
