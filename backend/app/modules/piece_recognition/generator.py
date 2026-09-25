"""Exercise 1 question generator: random position -> random question -> answer.

Flow per new puzzle::

    1. Take a validated FEN from the shared positions repository
       (puzzles.db when present, curated fallback otherwise).
    2. Pick one of the 16 target categories uniformly at random (12
       individual piece types + light/heavy groups, both colors) —
       deliberately NOT biased toward questions with existing pieces, so
       zero-target questions occur naturally.
    3. Compute the authoritative target squares server-side.
    4. Build the Persian prompt/explanation/hint and stage a validated
       ``Puzzle`` row. The answer lives only in ``answer_json`` and is never
       sent to the client (see ``PuzzleOut``).

Only the FEN column of puzzles.db is used; Moves/Rating/Themes are ignored.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.piece_recognition.categories import (
    CATEGORIES,
    CATEGORY_KEYS,
    Category,
)
from app.modules.piece_recognition.validator import SLUG, squares_for_target
from app.modules.positions import repository as positions
from app.modules.puzzles.models import SOURCE_GENERATED, Puzzle
from app.modules.puzzles.service import reusable_candidate_query, stage_validated_puzzle


def category_for(target_key: str) -> Category:
    """Look up a target category (individual or group)."""
    try:
        return CATEGORIES[target_key]
    except KeyError:
        raise ValueError("unknown_target") from None


def prompt_for_target(target_key: str) -> str:
    """Persian question text for a target category key."""
    return category_for(target_key).prompt_fa()


def explanation_for(target_key: str, squares: list[str]) -> str:
    """Persian explanation shown after answering."""
    return category_for(target_key).explanation_fa(squares)


def question_for_fen(fen: str, target_key: str) -> dict:
    """Pure question/answer builder for a FEN + category key (no DB, no random)."""
    category = category_for(target_key)
    if not positions.is_valid_fen(fen):
        raise ValueError("invalid_fen")
    squares = squares_for_target(fen, category.target_spec())
    return {
        "fen": fen,
        "target": target_key,
        "squares": squares,
        "prompt_fa": category.prompt_fa(),
        "explanation": category.explanation_fa(squares),
        "hint_json": {"hints": [{"id": "h1", "text_fa": category.hint_fa, "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> dict:
    """Pick a random position and a random target category for it."""
    rng = rng if rng is not None else random
    fen, _source = positions.random_position_fen(rng, explicit_path)
    target_key = rng.choice(CATEGORY_KEYS)
    return question_for_fen(fen, target_key)


def ensure_exercise(db: Session) -> None:
    if db.get(Exercise, SLUG) is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="تشخیص مهره",
                title_en="Piece Recognition",
                description="خانه‌های مهره‌های خواسته‌شده را روی صفحه پیدا کن.",
                is_active=True,
                sort_order=0,
            )
        )
        db.commit()


def _match_existing(
    db: Session, fen: str, target: str, exclude_ids: set[int]
) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists)."""
    candidates = (
        reusable_candidate_query(db, SLUG)
        .filter(Puzzle.fen == fen)
        .order_by(Puzzle.id)
        .all()
    )
    usable: Puzzle | None = None
    identical = False
    for puzzle in candidates:
        position = puzzle.position_json if isinstance(puzzle.position_json, dict) else {}
        if position.get("target") != target:
            continue
        identical = True
        if usable is None and puzzle.id not in exclude_ids:
            usable = puzzle
    return usable, identical


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
    *,
    source: str = SOURCE_GENERATED,
    source_reference: str | None = None,
) -> Puzzle:
    """Generate one random question and stage it as a validated candidate.

    The staged row plugs into the standard attempt flow unchanged
    (``POST /api/v1/attempts`` validates against the stored ``answer_json``).
    Identical (position, question) rows are reused, not duplicated;
    ``exclude_ids`` steers away from just-shown puzzles: a novel combo is
    created immediately, an excluded duplicate triggers a re-roll
    (bounded; best-effort).
    """
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, explicit_path)
    usable, identical = _match_existing(db, data["fen"], data["target"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, explicit_path)
            usable, identical = _match_existing(db, data["fen"], data["target"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = stage_validated_puzzle(
        db,
        {
            "exercise_slug": SLUG,
            "fen": data["fen"],
            "position_json": {"target": data["target"]},
            "answer_json": {"squares": data["squares"], "target": data["target"]},
            "hint_json": data["hint_json"],
            "prompt_fa": data["prompt_fa"],
            "explanation": data["explanation"],
            "initial_rating": 900.0,
        },
        source=source,
        source_reference=source_reference
        or (f"generator:{SLUG}" if source == SOURCE_GENERATED else f"{source}:{SLUG}"),
    )
    db.commit()
    db.refresh(puzzle)
    return puzzle
