"""Seed puzzles for Trapped Pieces.

Run:  python -m app.modules.trapped_pieces.seed
Idempotent: skips when puzzles for the slug already exist.

Unlike hand-listed seeds, this seed runs the authoritative pipeline:
it scans candidate source positions from the shared ``puzzles.db`` via
``generator.create_puzzle`` (seeded RNG for reproducibility), keeps only
positions with 1-3 trapped pieces, and reserves a single-answer subset
for Speed mode. Every stored answer is recomputed from the FEN with
``trapped_squares`` before insert, so rows are independently verifiable;
tests recompute them with the detector.

Seed plan (30 puzzles):
- 18 Practice puzzles (1-3 trapped pieces, at least 6 multi-answer).
- 12 Speed-pool puzzles (exactly one trapped piece each).

When the shared source is unavailable the generator falls back to its
curated positions, so seeding never crashes on a fresh machine.
"""

import random

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.puzzles.models import Puzzle
from app.modules.trapped_pieces import generator
from app.modules.trapped_pieces.detector import trapped_squares
from app.modules.trapped_pieces.validator import SLUG

SEED = 18
PRACTICE_COUNT = 18
SPEED_COUNT = 12
MIN_MULTI = 6


def seed_db(db: Session, rng: random.Random | None = None) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created.

    Idempotent top-up: rows stored under the pre-SEE definition (any
    stored answer that no longer matches a fresh recomputation, e.g.
    pawn answers) are ARCHIVED first (never hard-deleted, history kept),
    matching rows stay published, then fresh puzzles are generated until
    the Practice + Speed targets hold.
    """
    generator.ensure_exercise(db)

    stale = 0
    live = (
        db.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False)  # noqa: E712
        .all()
    )
    for row in live:
        stored = row.answer_json if isinstance(row.answer_json, dict) else {}
        squares = sorted(stored.get("squares", []))
        if (
            not squares  # this exercise never serves zero-target puzzles
            or (row.fen and squares != trapped_squares(row.fen))
        ):
            row.is_archived = True
            stale += 1
    if stale:
        db.commit()

    rng = rng if rng is not None else random.Random(SEED)
    created = 0

    def _counts() -> tuple[int, int, int]:
        rows = (
            db.query(Puzzle)
            .filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False)  # noqa: E712
            .all()
        )
        total = len(rows)
        multi = sum(1 for row in rows if len((row.answer_json or {}).get("squares", [])) > 1)
        single = sum(1 for row in rows if len((row.answer_json or {}).get("squares", [])) == 1)
        return total, multi, single

    def _done(total: int, multi: int, single: int) -> bool:
        return total >= PRACTICE_COUNT + SPEED_COUNT and multi >= MIN_MULTI and single >= SPEED_COUNT

    # Exclude every live id so identical-FEN reuse never double-counts a
    # row as created (the generator re-rolls bounded times instead).
    exclude: set[int] = {
        row.id
        for row in db.query(Puzzle.id)
        .filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False)  # noqa: E712
        .all()
    }
    guard = 0
    while guard < 200:
        total, multi, single = _counts()
        if _done(total, multi, single):
            break
        guard += 1
        # Fill the Speed pool with single-answer positions once Practice
        # variety (or size) is secured; otherwise take any 1-3 position.
        exactly_one = single < SPEED_COUNT and (multi >= MIN_MULTI or total >= PRACTICE_COUNT)
        puzzle = generator.create_puzzle(db, rng, exclude_ids=exclude, exactly_one=exactly_one)
        # Independent verification: the stored answer must equal a fresh
        # recomputation from the FEN (never trusted from the generator).
        assert puzzle.fen is not None
        assert puzzle.answer_json["squares"] == trapped_squares(puzzle.fen)
        if puzzle.id not in exclude:
            exclude.add(puzzle.id)
            created += 1
    return created


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        n = seed_db(db)
        print(f"seeded {n} trapped-pieces puzzles")
    finally:
        db.close()
