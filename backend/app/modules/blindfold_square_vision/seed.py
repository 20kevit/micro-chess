"""Seed/demo puzzles for Blindfold Square Vision.

Run:  python -m app.modules.blindfold_square_vision.seed
Idempotent: skips when puzzles for the slug already exist.

Entries carry the target square only; the color is always derived with
``square_color``, never stored. The small curated spread covers corners,
edges, and center squares in both colors; the generator serves uniform
random squares beyond these.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.blindfold_square_vision.generator import (
    EMPTY_FEN,
    explanation_for,
    prompt_for,
)
from app.modules.blindfold_square_vision.validator import SLUG, normalize_square, square_color
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle

# Curated spread: corners, edges, center — both colors.
SQUARES = ["a1", "h1", "a8", "h8", "d5", "e4", "c3", "f6"]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for square in SQUARES:
        if normalize_square(square) != square:
            raise ValueError(f"bad seed square: {square!r}")

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="خانه‌یابی ذهنی",
            title_en="Blindfold Square Vision",
            description="بگو خانه‌ی خواسته‌شده چه رنگی است.",
            is_active=True,
            sort_order=13,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for square in SQUARES:
        color = square_color(square)
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=EMPTY_FEN,
            position_json={"square": square, "mode": "standard"},
            answer_json={"square": square},
            hint_json={"hints": []},
            prompt_fa=prompt_for(square),
            explanation=explanation_for(square, color),
            initial_rating=800.0,
            is_published=True,
            is_archived=False,
        )
        db.add(puzzle)
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        n = seed_db(db)
        print(f"seeded {n} blindfold-square-vision puzzles")
    finally:
        db.close()
