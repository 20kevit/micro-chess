"""Trapped Pieces question generator: random FEN from the shared source.

Every puzzle comes from the shared ``puzzles.db`` (FEN only;
Moves/Rating/Themes ignored) via ``positions.repository``. The
authoritative answer is computed server-side with ``trapped_squares``
(legal moves + Static Exchange Evaluation, see ``detector.py``); the
puzzle's tactical theme or solution line is never the answer.

Selection policy (bounded, never an infinite loop):

1. Sample candidate FENs (up to ``MAX_CANDIDATES``).
2. Reject positions where either king is already in check (a piece
   trapped while its king is in check is a check-evasion question, not
   a trapped-piece question) and invalid FENs.
3. Practice accepts positions with 1-3 trapped pieces: empties are
   discarded (there is no "nothing trapped" question in this exercise)
   and 4+ degenerate back-rank-blocked positions are discarded.
4. Speed accepts ONLY positions with exactly one trapped piece, so one
   tap unambiguously grades +5/-4. Multi-answer positions are never
   served to Speed sessions.
5. Fall back to the first valid non-empty position when the scan finds
   nothing better (practically unreachable: ~43% of shared positions
   hold 1+ trapped pieces on measured data).

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
from app.modules.trapped_pieces.detector import (
    MAX_PRACTICE_TRAPPED,
    SLUG,
    either_king_in_check,
    trapped_squares,
)

PROMPT_FA = "کدام مهره‌ها گرفتار هستند؟"

HINT_FA = "مهره گرفتار جایی امن برای رفتن ندارد؛ حتی خانه‌ای که دشمن می‌زند امن است اگر پس گرفتنش به نفع ما تمام شود. شاه هم می‌تواند گرفتار باشد، ولی سرباز هرگز جواب نیست."

# This exercise's position in the roadmap (Exercise 18).
SORT_ORDER = 17

# Bounded random-selection loop (never infinite).
MAX_CANDIDATES = 25

# Curated fallback positions (used only when the shared source yields
# nothing usable, e.g. puzzles.db missing and fallback FENs exhausted).
# Each holds 1-2 trapped pieces under the authoritative detector;
# verified by tests.
CURATED_FENS: tuple[str, ...] = (
    "4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1",  # Na1 corner-trapped
    "2b1k3/1p1p4/8/8/8/8/8/4K3 w - - 0 1",  # Bc8 blocked by own pawns
    "4k3/8/8/8/8/8/P7/RN4K1 w - - 0 1",  # Ra1 boxed by Pa2 + Nb1
    "4k3/8/8/8/8/8/2PPP3/2BQK3 w - - 0 1",  # Qd1 boxed by own men
)


def explanation_for(squares: list[str]) -> str:
    if len(squares) == 1:
        return "۱ مهره گرفتار در صفحه است."
    return f"{len(squares)} مهره گرفتار در صفحه است."


def question_for_fen(fen: str, *, exactly_one: bool = False) -> dict:
    """Pure question/answer builder for a FEN (no DB, no random)."""
    if not positions.is_valid_fen(fen):
        raise ValueError("invalid_fen")
    if either_king_in_check(fen):
        raise ValueError("position_in_check")
    squares = trapped_squares(fen)
    if not squares:
        raise ValueError("no_trapped_piece")
    if exactly_one and len(squares) != 1:
        raise ValueError("not_single_trapped")
    if len(squares) > MAX_PRACTICE_TRAPPED:
        raise ValueError("too_many_trapped")
    return {
        "fen": fen,
        "squares": squares,
        "prompt_fa": PROMPT_FA,
        "explanation": explanation_for(squares),
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA, "rating_cost": 5}]},
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    *,
    exactly_one: bool = False,
) -> dict:
    """Pick a random shared position and build its question/answer data."""
    rng = rng if rng is not None else random
    # Fast path: keep the first valid FEN immediately when it already
    # satisfies the mode constraint (Practice: any 1-3, Speed: exactly 1).
    first = positions.random_position_fen(rng, explicit_path)
    first_data: dict | None = None
    try:
        first_data = question_for_fen(first[0], exactly_one=exactly_one)
    except ValueError:
        first_data = None
    if first_data is not None:
        return first_data
    # Otherwise search (bounded). Speed mode gets a wider budget because
    # single-answer positions are rarer (~19% of shared positions).
    budget = MAX_CANDIDATES * 3 if exactly_one else MAX_CANDIDATES
    for _ in range(budget):
        fen, _source = positions.random_position_fen(rng, explicit_path)
        try:
            return question_for_fen(fen, exactly_one=exactly_one)
        except ValueError:
            continue
    # Last resort (e.g. shared source missing and its fallback FENs hold
    # nothing usable): rotate the curated positions instead of crashing.
    for fen in CURATED_FENS:
        try:
            return question_for_fen(fen, exactly_one=exactly_one)
        except ValueError:
            continue
    raise ValueError("no_trapped_position_available")


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="مهره‌ی گرفتار",
                title_en="Trapped Piece",
                description="مهره‌هایی که هیچ راه فرار امنی ندارند را پیدا کن.",
                is_active=True,
                sort_order=SORT_ORDER,
            )
        )
        db.commit()
    else:
        changed = False
        if exercise.sort_order != SORT_ORDER:
            exercise.sort_order = SORT_ORDER
            changed = True
        if exercise.title_fa != "مهره‌ی گرفتار":
            exercise.title_fa = "مهره‌ی گرفتار"
            changed = True
        if changed:
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


def _rating_for(squares: list[str], rng: random.Random) -> float:
    base = 800.0 + len(squares) * 40.0 + rng.randrange(0, 60)
    return float(max(750.0, min(1250.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
    *,
    exactly_one: bool = False,
) -> Puzzle:
    """Generate one random question and persist it as a published puzzle.

    Practice uses ``exactly_one=False`` (1-3 trapped pieces); Speed
    sessions must pass ``exactly_one=True`` so every served position
    holds a single trapped piece.
    """
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, explicit_path, exactly_one=exactly_one)
    usable, identical = _match_existing(db, data["fen"], excluded)
    if usable is not None:
        answer = usable.answer_json if isinstance(usable.answer_json, dict) else {}
        squares = answer.get("squares", [])
        if exactly_one and len(squares) != 1:
            pass  # identical FEN with a stale/multi answer: keep sampling.
        else:
            return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, explicit_path, exactly_one=exactly_one)
            usable, identical = _match_existing(db, data["fen"], excluded)
            if usable is not None:
                answer = usable.answer_json if isinstance(usable.answer_json, dict) else {}
                squares = answer.get("squares", [])
                if exactly_one and len(squares) != 1:
                    continue
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={"fen": data["fen"], "mode": "standard"},
        answer_json={"squares": data["squares"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["squares"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
