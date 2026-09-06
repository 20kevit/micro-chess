"""Giving Check question generator: random FEN from the shared source.

Like Exercise 4, every puzzle comes from the shared ``puzzles.db`` (FEN
only; Moves/Rating/Themes ignored) via ``positions.repository``. The
authoritative answer is computed server-side with ``checking_moves``
(every legal non-King move that leaves the opponent in check).

Selection policy (bounded, never an infinite loop):

1. Sample candidate FENs (up to ``MAX_CANDIDATES``).
2. Reject positions where either king is already in check (the exercise
   asks which moves *give* check, not how to answer one).
3. Prefer a position with at least one checking move, but keep
   zero-target positions possible (``ZERO_TARGET_PROBABILITY`` accepts
   the first valid FEN immediately, so "no checks available" stays a
   real question).
4. Fall back to the first valid random position when no non-empty
   candidate appears.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` validates against the stored ``answer_json``).
Identical FEN rows are reused, not duplicated; ``exclude_ids`` steers away
from just-shown puzzles (bounded re-roll; best-effort).
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle
from app.modules.give_check.validator import SLUG, checking_moves, either_king_in_check

PROMPT_FA = "با کدام حرکت‌ها می‌توان کیش داد؟"

HINT_FA = "هر حرکت قانونی که بعد از آن شاه حریف کیش باشد جواب است؛ شاه هرگز کیش نمی‌دهد."

# This exercise's position in the roadmap (Exercise 5: after Undefended).
SORT_ORDER = 4

# Bounded random-selection loop (never infinite).
MAX_CANDIDATES = 25
# Fraction of puzzles that keep the first valid FEN immediately, so
# zero-target ("no checking move") questions occur naturally.
ZERO_TARGET_PROBABILITY = 0.15


def explanation_for(moves: list[str]) -> str:
    if not moves:
        return "هیچ حرکت کیش‌دهنده‌ای نیست؛ پس بدون فلش جواب را بررسی کن."
    return f"{len(moves)} حرکت کیش‌دهنده در صفحه است."


def question_for_fen(fen: str) -> dict:
    """Pure question/answer builder for a FEN (no DB, no random)."""
    if not positions.is_valid_fen(fen):
        raise ValueError("invalid_fen")
    if either_king_in_check(fen):
        raise ValueError("position_in_check")
    moves = checking_moves(fen)
    return {
        "fen": fen,
        "moves": moves,
        "prompt_fa": PROMPT_FA,
        "explanation": explanation_for(moves),
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA, "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> dict:
    """Pick a random shared position and build its question/answer data."""
    rng = rng if rng is not None else random
    # Fast path: keep the first valid FEN immediately when it already has
    # targets, or sometimes when it is empty, so zero-target ("no checking
    # move") questions stay a real but minority case.
    first = positions.random_position_fen(rng, explicit_path)
    first_data: dict | None = None
    try:
        first_data = question_for_fen(first[0])
    except ValueError:
        first_data = None
    if first_data is not None and first_data["moves"]:
        return first_data
    if first_data is not None and rng.random() < ZERO_TARGET_PROBABILITY:
        return first_data
    # Otherwise search for a non-empty position (bounded), falling back to
    # the first valid FEN (which may be zero-target).
    fallback = first_data
    for _ in range(MAX_CANDIDATES):
        fen, _source = positions.random_position_fen(rng, explicit_path)
        try:
            data = question_for_fen(fen)
        except ValueError:
            continue
        if fallback is None:
            fallback = data
        if data["moves"]:
            return data
    if fallback is not None:
        return fallback
    # Practically unreachable (fallbacks always parse), but never crash.
    fen, _source = positions.random_position_fen(rng, explicit_path)
    return question_for_fen(fen)


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="کیش دادن",
                title_en="Giving Check",
                description="همه حرکت‌های قانونی که شاه حریف را کیش می‌کنند را پیدا کن.",
                is_active=True,
                sort_order=SORT_ORDER,
            )
        )
        db.commit()
    elif exercise.sort_order != SORT_ORDER:
        # Roadmap renumbering (Exercise 5): keep upgraded DBs consistent.
        exercise.sort_order = SORT_ORDER
        db.commit()


def _match_existing(db: Session, fen: str, exclude_ids: set[int]) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists)."""
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


def _rating_for(moves: list[str], rng: random.Random) -> float:
    base = 800.0 + len(moves) * 8.0 + rng.randrange(0, 60)
    return float(max(700.0, min(1250.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one random question and persist it as a published puzzle."""
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
        position_json={"fen": data["fen"]},
        answer_json={"moves": data["moves"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["moves"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
