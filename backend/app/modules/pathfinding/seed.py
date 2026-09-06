"""Seed/demo puzzles for Pathfinding.

Run:  python -m app.modules.pathfinding.seed
Idempotent: skips when puzzles for the slug already exist.
Puzzles come from the deterministic generator (hand-designed templates
proven solvable by BFS); tests independently recompute reachability.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.pathfinding.generator import generate_all
from app.modules.pathfinding.validator import SLUG
from app.modules.puzzles.models import Puzzle


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    puzzles = generate_all()  # raises on any invalid template

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="مسیریابی",
            title_en="Pathfinding",
            description="مهره را قدم‌به‌قدم و امن به خانه ستاره‌دار برسان.",
            is_active=True,
            sort_order=6,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in puzzles:
        answer = {"fen": item["fen"], "from": item["from"], "target": item["target"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={"from": item["from"], "target": item["target"], "piece": item["kind"]},
            answer_json=answer,
            hint_json={"hints": item["hints"]},
            prompt_fa=item["prompt_fa"],
            explanation=item["explanation"],
            initial_rating=item["rating"],
            is_published=True,
            is_archived=False,
        )
        db.add(puzzle)
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        n = seed_db(db)
        print(f"seeded {n} pathfinding puzzles")
    finally:
        db.close()
