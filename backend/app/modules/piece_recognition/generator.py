"""Exercise 1 question generator: random position -> random question -> answer.

Flow per new puzzle::

    1. Take a validated FEN from the shared positions repository
       (puzzles.db when present, curated fallback otherwise).
    2. Pick one of the 12 canonical color x piece-type questions uniformly
       at random — deliberately NOT biased toward questions with existing
       pieces, so zero-target questions occur naturally.
    3. Compute the authoritative target squares server-side.
    4. Build the Persian prompt/explanation/hint and persist a published
       ``Puzzle`` row. The answer lives only in ``answer_json`` and is never
       sent to the client (see ``PuzzleOut``).

Only the FEN column of puzzles.db is used; Moves/Rating/Themes are ignored.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.piece_recognition.validator import (
    CANONICAL_TARGETS,
    SLUG,
    squares_for_target,
)
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle

# Persian names per piece kind (python-chess lowercase symbols).
PIECE_FA: dict[str, tuple[str, str]] = {
    # kind: (singular, plural)
    "p": ("سرباز", "سربازهای"),
    "n": ("اسب", "اسب‌های"),
    "b": ("فیل", "فیل‌های"),
    "r": ("رخ", "رخ‌های"),
    "q": ("وزیر", "وزیرهای"),
    "k": ("شاه", "شاه"),
}

COLOR_FA: dict[str, str] = {"white": "سفید", "black": "سیاه"}

HINT_FA: dict[str, str] = {
    "p": "سربازها قدم‌به‌قدم جلو می‌روند؛ ردیف‌های جلو را نگاه کن.",
    "n": "اسب به شکل L می‌پرد؛ وسط و گوشه‌های صفحه را نگاه کن.",
    "b": "فیل فقط روی خانه‌های هم‌رنگ خودش حرکت می‌کند.",
    "r": "رخ‌ها معمولاً در ستون‌ها و ردیف‌های باز ایستاده‌اند.",
    "q": "وزیر قوی‌ترین مهره است؛ اطراف شاه و مرکز را نگاه کن.",
    "k": "شاه معمولاً پشت مهره‌های خودش پنهان شده است.",
}


def prompt_for_target(target_key: str) -> str:
    """Persian question text for a canonical target key."""
    target = CANONICAL_TARGETS[target_key]
    kind = target["kinds"][0]
    singular, plural = PIECE_FA[kind]
    color = COLOR_FA[target["color"]]
    if kind == "k":
        return f"{singular} {color} را پیدا کن."
    return f"تمام {plural} {color} را پیدا کن."


def explanation_for(target_key: str, squares: list[str]) -> str:
    """Persian explanation shown after answering."""
    target = CANONICAL_TARGETS[target_key]
    kind = target["kinds"][0]
    singular, _ = PIECE_FA[kind]
    color = COLOR_FA[target["color"]]
    if not squares:
        return (
            f"در این وضعیت {singular} {color} وجود ندارد؛ "
            "پاسخ درست این است که هیچ خانه‌ای انتخاب نکنی."
        )
    joined = "، ".join(squares)
    return f"{singular} {color} در خانه‌های {joined} است."


def question_for_fen(fen: str, target_key: str) -> dict:
    """Pure question/answer builder for a FEN + target (no DB, no random)."""
    if target_key not in CANONICAL_TARGETS:
        raise ValueError("unknown_target")
    if not positions.is_valid_fen(fen):
        raise ValueError("invalid_fen")
    squares = squares_for_target(fen, CANONICAL_TARGETS[target_key])
    kind = CANONICAL_TARGETS[target_key]["kinds"][0]
    return {
        "fen": fen,
        "target": target_key,
        "squares": squares,
        "prompt_fa": prompt_for_target(target_key),
        "explanation": explanation_for(target_key, squares),
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA[kind], "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> dict:
    """Pick a random position and a random canonical question for it."""
    rng = rng if rng is not None else random
    fen, _source = positions.random_position_fen(rng, explicit_path)
    target_key = rng.choice(sorted(CANONICAL_TARGETS))
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


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> Puzzle:
    """Generate one random question and persist it as a published puzzle.

    The persisted row plugs into the standard attempt flow unchanged
    (``POST /api/v1/attempts`` validates against the stored ``answer_json``).
    """
    ensure_exercise(db)
    data = generate_question_data(rng, explicit_path)
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={"target": data["target"]},
        answer_json={"squares": data["squares"], "target": data["target"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=900.0,
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
