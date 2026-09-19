"""Puzzle service: publish locks the answer; archive instead of delete.

Phase 07: the canonical lifecycle state (``Puzzle.status``) is kept in
sync with the player-visibility booleans here so every caller shares
one rule. Rows constructed directly as already-published (runtime
exercise generators, seeds) enter the lifecycle as ``published`` via
the model default; admin-managed transitions go through
``app.modules.admin.service`` which additionally records history,
validation/review rows, and audit records.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.puzzles.models import (
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_RETIRED,
    Puzzle,
)


class AnswerImmutableError(ValueError):
    pass


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
    # Definitive answer becomes immutable once published.
    if puzzle.is_published:
        raise AnswerImmutableError("answer is immutable once published")
    puzzle.answer_json = answer_json
    db.commit()
    db.refresh(puzzle)
    return puzzle


def archive(db: Session, puzzle: Puzzle) -> Puzzle:
    # Never hard-delete puzzles with history; archive/deactivate instead.
    puzzle.is_archived = True
    puzzle.status = STATUS_RETIRED
    puzzle.retired_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def visible_query(db: Session, exercise_slug: str | None = None):
    # Player-visibility projection plus canonical lifecycle guard, so a
    # flag/status desync can never leak quarantined/rejected content into
    # the read path (submit and recommendations already guard status).
    q = db.query(Puzzle).filter(
        Puzzle.is_published == True,  # noqa: E712
        Puzzle.is_archived == False,  # noqa: E712
        Puzzle.status == STATUS_PUBLISHED,
    )
    if exercise_slug:
        q = q.filter(Puzzle.exercise_slug == exercise_slug)
    return q
