"""Attempt submission: Puzzle -> Validation -> Score -> Evidence ->
Rating -> Gamification -> Feedback.

Backend is authoritative. Frontend never decides correctness.
Practice attempts never affect rating (rating snapshot stays NULL), but
both practice and rated attempts by authenticated users earn XP (XP
snapshot stays NULL only for guests and terminal states).
Rated attempts update the player's per-exercise rating through the
rating engine; qualifying attempts update gamification through the
gamification engine; attempt, rating, XP, streak, and achievement state
commit atomically. An optional P6 assignment/assessment context
(server-validated, write-once) records which direct work or evaluation
session the attempt belongs to without changing any of the above.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.exercises import registry
from app.modules.exercises.models import Exercise
from app.modules.evidence import service as evidence_service
from app.modules.feedback_engine.service import feedback_key_for
from app.modules.gamification_engine import service as gamification_service
from app.modules.progress.models import Attempt
from app.modules.puzzles import service as puzzle_service
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine import service as rating_service
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
    assignment_id: int | None = None,
    assessment_id: int | None = None,
) -> tuple[Attempt, str, dict]:
    try:
        puzzle = puzzle_service.require_visible_puzzle(db, puzzle_id)
    except puzzle_service.PlayerPuzzleUnavailableError as exc:
        raise ValueError("puzzle_not_available") from exc
    # Disabled exercises cannot start new training work (Phase 6 admin).
    # Missing catalog rows (legacy/generated content without an Exercise
    # entry) stay playable so pre-admin behavior is preserved; history is
    # never invalidated either way.
    exercise = db.get(Exercise, puzzle.exercise_slug)
    if exercise is not None and not exercise.is_active:
        raise ValueError("exercise_not_available")

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

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user_id is not None and guest_session_id is not None:
        raise ValueError("attempt_owner_conflict")
    # Guest practice is disabled (product decision): only authenticated
    # users may create attempts (and therefore evidence). Historical guest
    # rows stay untouched; migration moves them without this function.
    if user_id is None:
        raise ValueError("auth_required")
    # P6 assignment/assessment context (server-validated, write-once).
    # Unknown, foreign, or terminally-closed rows are rejected; practice
    # attempts simply omit both. The link changes nothing about
    # validation, scoring, rating, XP, or evidence -- it only records
    # which direct work / evaluation session the attempt belongs to.
    if assignment_id is not None:
        from app.modules.relationships import service as relationship_service

        relationship_service.get_assignable_for_attempt(
            db, user_id=user_id, assignment_id=assignment_id
        )
    if assessment_id is not None:
        from app.modules.assessments import service as assessment_service

        assessment_service.resolve_for_attempt(
            db, user_id=user_id, assessment_id=assessment_id
        )
    # Daily quota (Free 10 / Premium 100 per user-local day): only
    # validated correct/partial/wrong attempts consume it, and only
    # after every other rejection gate above has passed. Terminal
    # client states and rejected submissions never reach this call, so
    # existing attempt semantics are preserved exactly. The check runs
    # before the attempt row is written, inside this same transaction.
    if result.value in ("correct", "partial", "wrong"):
        from app.modules.quota import service as quota_service

        quota_service.check_and_consume(db, user_id)
    attempt = Attempt(
        user_id=user_id,
        guest_session_id=guest_session_id,
        puzzle_id=puzzle.id,
        exercise_slug=puzzle.exercise_slug,
        mode=mode.value,
        result=result.value,
        answer_json=answer,
        score=score,
        rating_delta=None,
        assignment_id=assignment_id,
        assessment_id=assessment_id,
        # P1 historical snapshot: difficulty/rating context at submit time.
        # Write-once here; no update path exists for attempts, so later
        # puzzle-metadata edits can never rewrite this record.
        puzzle_rating_snapshot=puzzle.initial_rating,
        difficulty_snapshot=puzzle.difficulty,
        started_at=started_at.replace(tzinfo=None) if started_at and started_at.tzinfo else started_at,
        duration_ms=_duration_ms(started_at, now),
        hints_used=used_hints,
        # P2 validator detail snapshot (server-authoritative, write-once).
        validation_detail=dict(detail),
    )
    db.add(attempt)
    db.flush()

    # P2 evidence pipeline (validator -> result -> mistake -> evidence):
    # classification reads the validator detail + raw answers and
    # persists append-only evidence rows in this same transaction, so
    # attempt + evidence commit atomically. Rating is untouched:
    # mistakes feed evidence only, never rating deltas.
    evidence_service.generate_for_attempt(
        db,
        attempt=attempt,
        result=result.value,
        detail=detail,
        raw_answer=answer if isinstance(answer, dict) else {},
        puzzle_answer=dict(puzzle.answer_json) if isinstance(puzzle.answer_json, dict) else {},
        hints_used=used_hints,
    )

    # Server-decided rated/unrated: only an authenticated user's validated
    # correct/partial/wrong attempt in rated mode touches ratings. The
    # rating application flushes (no commit); the single commit below
    # persists attempt + rating + event atomically.
    if rating_service.is_rating_eligible(mode=mode, user_id=user_id, result=result.value):
        assert user_id is not None
        rating_service.apply_rated_attempt(
            db,
            user_id=user_id,
            exercise_slug=puzzle.exercise_slug,
            attempt=attempt,
            result=result.value,
            puzzle_rating=puzzle.initial_rating,
        )

    # Server-decided XP: any authenticated user's validated
    # correct/partial/wrong attempt earns XP in both practice and rated
    # modes (gamification eligibility is separate from rating
    # eligibility). The gamification application flushes (no commit);
    # the single commit below persists attempt + rating + XP + streak +
    # achievements atomically.
    if gamification_service.is_xp_eligible(user_id=user_id, result=result.value):
        assert user_id is not None
        gamification_service.apply_attempt(
            db,
            user_id=user_id,
            attempt=attempt,
            result=result.value,
            active_date=now.date(),
        )

    db.commit()
    db.refresh(attempt)
    return attempt, feedback_key, detail
