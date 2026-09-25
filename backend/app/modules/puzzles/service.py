"""Puzzle service: publish locks the answer; archive instead of delete."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.puzzles.models import (
    PUZZLE_SOURCES,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_RETIRED,
    STATUS_REVIEWED,
    STATUS_VALIDATED,
    Puzzle,
    PuzzleStatusHistory,
    PuzzleValidation,
)
from app.modules.puzzles.validation import CONTENT_VALIDATOR_VERSION, validate_puzzle_fields


class AnswerImmutableError(ValueError):
    pass


class PuzzleCandidateValidationError(ValueError):
    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__("puzzle_candidate_invalid")


class DuplicatePuzzleCandidateError(PuzzleCandidateValidationError):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__(errors)
        duplicate = next(
            (error for error in errors if error.get("code") == "duplicate_content"),
            {},
        )
        self.duplicate_of = duplicate.get("duplicate_of")


class PlayerPuzzleUnavailableError(LookupError):
    code = "puzzle_not_available"


def _load_content_validators() -> None:
    from app.modules.captures import content as _captures_content  # noqa: F401
    from app.modules.legal_destinations import content as _legal_content  # noqa: F401
    from app.modules.piece_recognition import content as _piece_content  # noqa: F401


def stage_validated_puzzle(
    db: Session,
    fields: dict[str, Any],
    *,
    source: str,
    source_reference: str,
    actor_id: int | None = None,
    generator_run_id: int | None = None,
    validation_metadata: dict[str, Any] | None = None,
    history_reason: str = "candidate validated",
) -> Puzzle:
    """Validate and stage one candidate without committing or publishing it."""
    if source not in PUZZLE_SOURCES:
        raise ValueError("invalid_source")
    reference = str(source_reference or "").strip()
    if not reference:
        raise ValueError("source_reference_required")
    if len(reference) > 255:
        raise ValueError("source_reference_too_long")

    candidate = dict(fields)
    slug = str(candidate.get("exercise_slug") or "").strip()
    fen = candidate.get("fen")
    position_json = candidate.get("position_json") or {}
    answer_json = candidate.get("answer_json") or {}
    hint_json = candidate.get("hint_json") or {}
    prompt_fa = str(candidate.get("prompt_fa") or "")
    explanation = str(candidate.get("explanation") or "")
    initial_rating = float(candidate.get("initial_rating", 1200.0))
    difficulty = candidate.get("difficulty")
    target_rating = candidate.get("target_rating")
    if target_rating is not None:
        target_rating = float(target_rating)

    _load_content_validators()
    outcome = validate_puzzle_fields(
        db,
        exercise_slug=slug,
        fen=fen,
        position_json=position_json,
        answer_json=answer_json,
        difficulty=difficulty,
        target_rating=target_rating,
        initial_rating=initial_rating,
        prompt_fa=prompt_fa,
        explanation=explanation,
    )
    if not outcome.ok:
        if any(error.get("code") == "duplicate_content" for error in outcome.errors):
            raise DuplicatePuzzleCandidateError(outcome.errors)
        raise PuzzleCandidateValidationError(outcome.errors)

    puzzle = Puzzle(
        exercise_slug=slug,
        fen=fen,
        position_json=position_json,
        answer_json=answer_json,
        hint_json=hint_json,
        prompt_fa=prompt_fa[:500],
        explanation=explanation[:2000],
        initial_rating=initial_rating,
        is_published=False,
        is_archived=False,
        status=STATUS_VALIDATED,
        source=source,
        source_reference=reference,
        generator_run_id=generator_run_id,
        difficulty=difficulty,
        target_rating=target_rating,
        content_hash=outcome.content_hash,
    )
    db.add(puzzle)
    db.flush()
    metadata = dict(validation_metadata or {})
    metadata.setdefault("errors", [])
    db.add(
        PuzzleValidation(
            puzzle_id=puzzle.id,
            validator_version=CONTENT_VALIDATOR_VERSION,
            status="pass",
            result_json=metadata,
            validated_by_user_id=actor_id,
        )
    )
    db.add(
        PuzzleStatusHistory(
            puzzle_id=puzzle.id,
            from_status=STATUS_DRAFT,
            to_status=STATUS_VALIDATED,
            changed_by_user_id=actor_id,
            reason=history_reason[:500],
        )
    )
    db.flush()
    return puzzle


def create_draft(db: Session, **fields) -> Puzzle:
    fields.setdefault("status", STATUS_DRAFT)
    puzzle = Puzzle(is_published=False, **fields)
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def publish(db: Session, puzzle: Puzzle) -> Puzzle:
    puzzle.is_published = True
    puzzle.published_at = datetime.now(timezone.utc)
    puzzle.status = STATUS_PUBLISHED
    db.commit()
    db.refresh(puzzle)
    return puzzle


def update_answer(db: Session, puzzle: Puzzle, answer_json: dict) -> Puzzle:
    if puzzle.is_published:
        raise AnswerImmutableError("answer is immutable once published")
    puzzle.answer_json = answer_json
    db.commit()
    db.refresh(puzzle)
    return puzzle


def archive(db: Session, puzzle: Puzzle) -> Puzzle:
    puzzle.is_archived = True
    puzzle.status = STATUS_RETIRED
    puzzle.retired_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def visible_query(db: Session, exercise_slug: str | None = None):
    q = db.query(Puzzle).filter(
        Puzzle.is_published == True,  # noqa: E712
        Puzzle.is_archived == False,  # noqa: E712
        Puzzle.status == STATUS_PUBLISHED,
    )
    if exercise_slug:
        q = q.filter(Puzzle.exercise_slug == exercise_slug)
    return q


def reusable_candidate_query(db: Session, exercise_slug: str):
    return db.query(Puzzle).filter(
        Puzzle.exercise_slug == exercise_slug,
        Puzzle.is_archived == False,  # noqa: E712
        Puzzle.status.in_(
            (STATUS_VALIDATED, STATUS_REVIEWED, STATUS_APPROVED, STATUS_PUBLISHED)
        ),
    )


def require_visible_puzzle(
    db: Session,
    puzzle_id: int,
    exercise_slug: str | None = None,
) -> Puzzle:
    puzzle = visible_query(db, exercise_slug).filter(Puzzle.id == puzzle_id).first()
    if puzzle is None:
        raise PlayerPuzzleUnavailableError("puzzle_not_available")
    return puzzle


def player_puzzle(
    db: Session,
    exercise_slug: str,
    *,
    exclude_ids: set[int] | None = None,
    answer_matches: Callable[[dict[str, Any]], bool] | None = None,
) -> Puzzle:
    query = visible_query(db, exercise_slug)
    excluded = set(exclude_ids or ())
    if excluded:
        query = query.filter(Puzzle.id.not_in(excluded))
    puzzles = query.order_by(Puzzle.id).all()
    for puzzle in puzzles:
        answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
        if answer_matches is None or answer_matches(answer):
            return puzzle
    raise PlayerPuzzleUnavailableError("puzzle_not_available")
