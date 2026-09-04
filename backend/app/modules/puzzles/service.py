"""Puzzle service: publish locks the answer; archive instead of delete."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.puzzles.models import Puzzle


class AnswerImmutableError(ValueError):
    pass


def create_draft(db: Session, **fields) -> Puzzle:
    puzzle = Puzzle(is_published=False, **fields)
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def publish(db: Session, puzzle: Puzzle) -> Puzzle:
    puzzle.is_published = True
    puzzle.published_at = datetime.now(timezone.utc)
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
    db.commit()
    db.refresh(puzzle)
    return puzzle


def visible_query(db: Session, exercise_slug: str | None = None):
    q = db.query(Puzzle).filter(Puzzle.is_published == True, Puzzle.is_archived == False)  # noqa: E712
    if exercise_slug:
        q = q.filter(Puzzle.exercise_slug == exercise_slug)
    return q
