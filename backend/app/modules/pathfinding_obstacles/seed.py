"""Seed/demo puzzles for Exercise 7 (Pathfinding with Obstacles).

Run:  python -m app.modules.pathfinding_obstacles.seed
Idempotent: skips when puzzles for the slug already exist.
Puzzles come from the solved, quality-gated generator with a fixed seed,
so seeding is deterministic; every puzzle carries a BFS-verified
``optimal_moves`` stored server-side (never exposed).
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.pathfinding_obstacles import generator as gen
from app.modules.pathfinding_obstacles.validator import SLUG
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle

SEED_COUNT = 15


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    import random

    gen.ensure_exercise(db)
    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0
    rng = random.Random(7007)
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
        print(f"seeded {n} obstacle-pathfinding puzzles")
    finally:
        db.close()
