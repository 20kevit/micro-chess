"""Seed/demo puzzles for Pathfinding (Exercise 6, simple version).

Run:  python -m app.modules.pathfinding.seed
Idempotent: skips when puzzles for the slug already exist.
Puzzles come from the weighted random generator with a fixed seed, so
seeding is deterministic; every puzzle is reachable by construction and
its BFS optimal distance is stored server-side (never exposed).
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.pathfinding import generator as gen
from app.modules.pathfinding.validator import SLUG
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle

SEED_COUNT = 15


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    import random

    gen.ensure_exercise(db)
    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0
    rng = random.Random(6006)
    created = 0
    for _ in range(SEED_COUNT):
        gen.create_puzzle(
            db,
            rng,
            source=SOURCE_IMPORTED,
            source_reference=f"seed:{SLUG}",
        )
        created += 1
    return created


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        n = seed_db(db)
        print(f"seeded {n} pathfinding puzzles")
    finally:
        db.close()
