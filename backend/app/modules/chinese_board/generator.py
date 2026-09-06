"""Chinese Board question generator: real positions, exact recall.

Every puzzle comes from the shared ``puzzles.db`` (FEN only;
Moves/Rating/Themes ignored) via ``positions.repository``. The FEN stored
in the project's database is the single authority for both the board shown
during memorization and the answer used at grading — the client never
supplies the original position.

Selection policy (bounded, never an infinite loop):

1. Sample candidate FENs (up to ``MAX_CANDIDATES`` per puzzle) via
   ``positions.random_position_fen`` (indexed rowid probing; the table is
   never loaded into memory).
2. Accept the first valid candidate. No difficulty gate and no piece-count
   filter: the count is naturally bounded by chess (<= 32 pieces, so the
   study budget ``piece_count * 400ms`` spans ~1.6s-12.8s on real data)
   and every real position is a fair memory question.
3. Fall back to a curated fallback FEN evaluated the same way.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` validates against the stored ``answer_json``).
Identical FEN rows are reused, not duplicated; ``exclude_ids`` steers
away from just-shown puzzles (bounded re-roll; best-effort).
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.chinese_board import pieces as cb
from app.modules.chinese_board.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "این صفحه را حفظ کن و بعد از نو بچین."

HINT_FA = "مهره‌ها را دسته‌دسته حفظ کن: اول شاه‌ها، بعد مهره‌های بزرگ، بعد سربازها."

# Bounded random-selection loop (never infinite). Any valid FEN is
# acceptable, so a handful of candidates always suffices.
MAX_CANDIDATES = 10


def question_for_fen(fen: str) -> dict | None:
    """Pure question/answer builder for a FEN (no DB, no random).

    Returns None when the FEN is invalid. Every valid position is
    eligible — piece count only sets the study budget.
    """
    if not positions.is_valid_fen(fen):
        return None
    try:
        count = cb.piece_count(fen)
    except ValueError:
        return None
    return {
        "fen": fen,
        "piece_count": count,
        "memorization_ms": count * cb.MEMORIZE_MS_PER_PIECE,
        "prompt_fa": PROMPT_FA,
        "explanation": f"این صفحه {count} مهره داشت.",
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA, "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> dict:
    """Pick a random real position (any valid FEN is eligible)."""
    rng = rng if rng is not None else random
    fallback: dict | None = None
    for _ in range(MAX_CANDIDATES):
        fen, _source = positions.random_position_fen(rng, explicit_path)
        data = question_for_fen(fen)
        if data is None:
            continue
        return data
    if fallback is not None:  # pragma: no cover - defensive
        return fallback
    # Practically unreachable (any valid FEN is accepted), but never
    # crash: evaluate curated fallbacks the same way.
    for fen in positions.FALLBACK_FENS:
        data = question_for_fen(fen)
        if data is not None:
            return data
    raise RuntimeError("could not generate a chinese-board puzzle")


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="صفحه چینی",
                title_en="Chinese Board",
                description="صفحه را حفظ کن و از نو بچین.",
                is_active=True,
                sort_order=13,
            )
        )
        db.commit()
    else:
        changed = False
        if exercise.title_fa != "صفحه چینی":
            exercise.title_fa = "صفحه چینی"
            changed = True
        if exercise.title_en != "Chinese Board":
            exercise.title_en = "Chinese Board"
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


def _rating_for(count: int, rng: random.Random) -> float:
    base = 750.0 + count * 8.0 + rng.randrange(0, 60)
    return float(max(700.0, min(1250.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one random memory question and persist it published."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, explicit_path)
    usable, identical = _match_existing(db, data["fen"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, explicit_path)
            usable, identical = _match_existing(db, data["fen"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={
            "fen": data["fen"],
            "piece_count": data["piece_count"],
            "memorization_ms": data["memorization_ms"],
            "mode": "standard",
        },
        answer_json={"fen": data["fen"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["piece_count"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
