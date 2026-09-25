"""Blindfold Square Vision question generator: one uniform random square.

Every puzzle asks for the color of a single square drawn uniformly from
all 64 squares. The square itself is the public question
(``position_json``); only its color is secret, and the color is always
derived with ``square_color`` — never stored. ``fen`` is the empty board
so Practice can render a tappable board with the shared board zone.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` validates against the stored
``answer_json``). Identical square rows are reused, not duplicated;
``exclude_ids`` steers away from just-shown puzzles (bounded re-roll;
best-effort).
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.blindfold_square_vision.validator import SLUG, normalize_square
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_GENERATED, Puzzle
from app.modules.puzzles.service import reusable_candidate_query, stage_validated_puzzle

EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"

FILES = "abcdefgh"


def prompt_for(square: str) -> str:
    return f"خانه‌ی {square} چه رنگیه؟"


def explanation_for(square: str, color: str) -> str:
    name = "سفید" if color == "white" else "سیاه"
    return f"خانه‌ی {square} {name} است."


def random_square(rng: random.Random | None = None) -> str:
    """Uniform random square name across all 64 squares."""
    rng = rng if rng is not None else random
    return f"{rng.choice(FILES)}{rng.randrange(1, 9)}"


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="خانه‌یابی ذهنی",
                title_en="Blindfold Square Vision",
                description="بگو خانه‌ی خواسته‌شده چه رنگی است.",
                is_active=True,
                sort_order=13,
            )
        )
        db.commit()


def _match_existing(db: Session, square: str, exclude_ids: set[int]) -> Puzzle | None:
    """Return a usable candidate row for the square, or None."""
    candidates = reusable_candidate_query(db, SLUG).order_by(Puzzle.id).all()
    for puzzle in candidates:
        answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
        if normalize_square(answer.get("square")) == square and puzzle.id not in exclude_ids:
            return puzzle
    return None


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
    *,
    source: str = SOURCE_GENERATED,
    source_reference: str | None = None,
) -> Puzzle:
    """Generate one uniform-random square question and stage it as validated."""
    from app.modules.blindfold_square_vision.validator import square_color

    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    square = random_square(rng)
    usable = _match_existing(db, square, excluded)
    if usable is None:
        for _ in range(10):
            candidate = random_square(rng)
            usable = _match_existing(db, candidate, excluded)
            if usable is not None:
                square = candidate
                break
    if usable is not None:
        return usable
    color = square_color(square)
    puzzle = stage_validated_puzzle(
        db,
        {
            "exercise_slug": SLUG,
            "fen": EMPTY_FEN,
            "position_json": {"square": square, "mode": "standard"},
            "answer_json": {"square": square},
            "hint_json": {"hints": []},
            "prompt_fa": prompt_for(square),
            "explanation": explanation_for(square, color),
            "initial_rating": 800.0,
        },
        source=source,
        source_reference=source_reference
        or (f"generator:{SLUG}" if source == SOURCE_GENERATED else f"{source}:{SLUG}"),
    )
    db.commit()
    db.refresh(puzzle)
    return puzzle
