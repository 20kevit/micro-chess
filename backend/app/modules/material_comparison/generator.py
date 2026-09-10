"""Heavier Side question generator: real positions, material only.

Every puzzle comes from the shared ``puzzles.db`` (FEN only;
Moves/Rating/Themes ignored) via ``positions.repository``. The FEN stored
in the project's database is used exactly as exposed — no solution moves
are applied. The authoritative answer is recomputed server-side from the
displayed FEN with the isolated ``material`` calculator.

Selection policy (bounded, never an infinite loop):

1. Pick a desired answer category uniformly (white / black / equal) so
   served puzzles stay roughly balanced over time.
2. Sample candidate FENs (up to ``MAX_CANDIDATES`` per puzzle) via
   ``positions.random_position_fen`` (indexed rowid probing; the table is
   never loaded into memory).
3. Accept the first candidate that satisfies the 10% difficulty gate
   AND matches the desired category.
4. Fall back to the first 10%-eligible candidate (any category) when the
   desired category does not appear in bounds, then to a curated
   fallback FEN evaluated the same way.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` validates against the stored ``answer_json``).
Identical FEN rows are reused, not duplicated; ``exclude_ids`` steers
away from just-shown puzzles (bounded re-roll; best-effort).
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.material_comparison import material as mat
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle
from app.modules.material_comparison.validator import SLUG

PROMPT_FA = "کدام طرف جلوتر است؟"

HINT_FA = "ارزش مهره‌ها: سرباز ۱، اسب ۳، فیل ۳، رخ ۵، وزیر ۹، شاه صفر. هر طرف را جداگانه جمع بزن."

# Bounded random-selection loop (never infinite). The 10% gate accepts
# ~70% of real puzzle positions, so 40 candidates almost always hit even
# a specific category.
MAX_CANDIDATES = 40

CATEGORIES = ("white", "black", "equal")


def explanation_for(white: int, black: int, expected: str) -> str:
    if expected == "white":
        return "سفید جلوتر بود."
    if expected == "black":
        return "سیاه جلوتر بود."
    return "مهره‌ها مساوی بودند."


def question_for_fen(fen: str) -> dict | None:
    """Pure question/answer builder for a FEN (no DB, no random).

    Returns None when the FEN is invalid or fails the 10% difficulty gate.
    """
    if not positions.is_valid_fen(fen):
        return None
    try:
        white, black = mat.material_from_fen(fen)
    except ValueError:
        return None
    if not mat.is_material_difference_acceptable(white, black):
        return None
    expected = mat.classify(white, black)
    return {
        "fen": fen,
        "white": white,
        "black": black,
        "expected": expected,
        "prompt_fa": PROMPT_FA,
        "explanation": explanation_for(white, black, expected),
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA, "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    desired: str | None = None,
) -> dict:
    """Pick a random eligible position, preferring a balanced category."""
    rng = rng if rng is not None else random
    want = desired if desired in CATEGORIES else rng.choice(CATEGORIES)
    fallback: dict | None = None
    for _ in range(MAX_CANDIDATES):
        fen, _source = positions.random_position_fen(rng, explicit_path)
        data = question_for_fen(fen)
        if data is None:
            continue
        if fallback is None:
            fallback = data
        if data["expected"] == want:
            return data
    if fallback is not None:
        return fallback
    # Practically unreachable (the gate accepts most positions), but never
    # crash: evaluate curated fallbacks the same way.
    for fen in positions.FALLBACK_FENS:
        data = question_for_fen(fen)
        if data is not None:
            return data
    raise RuntimeError("could not generate an eligible heavier-side puzzle")


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="کدام طرف سنگین‌تر است؟",
                title_en="Heavier Side",
                description="بگو کدام طرف مهره‌های ارزشمندتری دارد.",
                is_active=True,
                sort_order=9,
            )
        )
        db.commit()
    else:
        changed = False
        if exercise.title_fa != "کدام طرف سنگین‌تر است؟":
            exercise.title_fa = "کدام طرف سنگین‌تر است؟"
            changed = True
        if exercise.title_en != "Heavier Side":
            exercise.title_en = "Heavier Side"
            changed = True
        if changed:
            db.commit()


def _match_existing(db: Session, fen: str, exclude_ids: set[int]) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists). FEN-shaped rows only."""
    candidates = (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == SLUG,
            Puzzle.is_published == True,  # noqa: E712
            Puzzle.is_archived == False,  # noqa: E712
            Puzzle.fen == fen,
        )
        .order_by(Puzzle.id)
        .all()
    )
    usable: Puzzle | None = None
    identical = False
    for puzzle in candidates:
        identical = True
        if usable is None and puzzle.id not in exclude_ids:
            usable = puzzle
    return usable, identical


def _rating_for(white: int, black: int, rng: random.Random) -> float:
    base = 750.0 + max(white, black) * 4.0 + abs(white - black) * 8.0 + rng.randrange(0, 60)
    return float(max(700.0, min(1250.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
    desired: str | None = None,
) -> Puzzle:
    """Generate one random eligible question and persist it published."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, explicit_path, desired)
    usable, identical = _match_existing(db, data["fen"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, explicit_path, desired)
            usable, identical = _match_existing(db, data["fen"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={"fen": data["fen"], "mode": "standard"},
        answer_json={"fen": data["fen"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["white"], data["black"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
