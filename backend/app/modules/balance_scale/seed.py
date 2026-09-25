"""Seed/demo puzzles for Balance Scale (Exercise 10, ترازو).

Run:  python -m app.modules.balance_scale.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified (4–10 valid pieces, no kings,
target solvable within 10 pieces with optimal<=10) before insert;
invalid entries fail loudly instead of seeding a broken puzzle.
Validation itself never depends on one stored solution: any exact
combination is accepted, and the optimal count is recomputed server-side.

Note: with the 4-piece left minimum, single-piece optimals (targets
9/5/3/1) cannot occur — every seed below needs >= 2 white pieces.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.balance_scale import generator as gen
from app.modules.balance_scale import solver
from app.modules.balance_scale.generator import PROMPT_FA
from app.modules.balance_scale.validator import SLUG, normalize_piece, total_value
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

# Hand-designed left pans of rising difficulty, covering the required
# edge cases (targets 4/6/8/9-family/10/18/90) and multi-solution cases
# (e.g. 10 = 9+1 or 5+5; 18 = 9+9 or 5+5+5+3).
SEED_LEFTS: list[list[str]] = [
    ["p", "p", "p", "p"],  # 4 -> optimal 4 (1+1+1+1); also solvable 3+1
    ["n", "p", "p", "p"],  # 6 -> optimal 2 (3+3)
    ["n", "n", "p", "p"],  # 8 -> optimal 2 (5+3)
    ["q", "p", "p", "p"],  # 12 -> optimal 4, queen-led pan
    ["r", "r"],  # 10 is 2 pieces; pad to 4 below (see verify: replaced)
    ["q", "q"],  # 18 -> optimal 2 (9+9); padded to 4 below
    ["q", "r", "b"],  # 17 -> optimal 3 (9+5+3); padded to 4 below
    ["r", "r", "p", "p"],  # 12 -> optimal 4 (5+5+1+1)
    ["q", "b", "n", "p"],  # 16 -> optimal 4 (9+5+1+1)
    ["q", "r", "n", "p", "p"],  # 19 -> optimal 3 (9+9+1)
    ["r", "r", "b", "b", "p", "p"],  # 18 from six pieces
    ["q", "q", "r", "b", "p"],  # 31 -> optimal 5
    ["q", "q", "q", "r", "n", "p"],  # 40 -> optimal 6
    ["q", "q", "q", "q", "r", "r", "n"],  # 54 -> optimal 6 (9x6)
    ["q", "q", "q", "q", "q", "q", "q", "q", "q", "q"],  # 90 -> optimal 10
]

# Two-piece pans above violate the 4-piece minimum; expand them to legal
# 4-piece pans with nearby instructive targets.
SEED_FIXUPS: dict[int, list[str]] = {
    4: ["n", "n", "p", "p", "p", "p"],  # 10 -> optimal 2 (9+1 or 5+5)
    5: ["q", "q", "p", "p"],  # 20 -> optimal 4 (9+9+1+1)
    6: ["q", "r", "b", "p"],  # 18 -> optimal 2 (9+9)
}


def verify_left(left: list[str]) -> tuple[int, int]:
    """Independently verify one left pan. Returns (target, optimal)."""
    if not isinstance(left, list) or not (4 <= len(left) <= 10):
        raise ValueError(f"left pan needs 4-10 pieces: {left}")
    clean = [normalize_piece(p) for p in left]
    if any(p is None for p in clean):
        raise ValueError(f"invalid piece (kings forbidden): {left}")
    target = total_value([p for p in clean if p is not None])
    optimal = solver.optimal_count(target)
    if optimal is None or optimal > 10:
        raise ValueError(f"target {target} not solvable within 10 pieces: {left}")
    return target, optimal


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    gen.ensure_exercise(db)
    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    lefts = [list(pan) for pan in SEED_LEFTS]
    for idx, fix in SEED_FIXUPS.items():
        lefts[idx] = list(fix)
    for left in lefts:
        verify_left(left)

    created = 0
    for left in lefts:
        target, optimal = verify_left(left)
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": None,
                "position_json": {"left": left},
                "answer_json": {"left": left, "target": target, "optimal_count": optimal},
                "hint_json": {
                    "hints": [
                        {"id": "h1", "text_fa": "اول ارزش همه مهره‌های سیاه را جمع بزن.", "rating_cost": 5},
                    ]
                },
                "prompt_fa": PROMPT_FA,
                "explanation": f"مجموع کفه سیاه {target} است؛ با کمترین مهره به همین عدد برس.",
                "initial_rating": float(max(700.0, min(1350.0, 750.0 + target * 6.0 + optimal * 10.0))),
            },
            source=SOURCE_IMPORTED,
            source_reference=f"seed:{SLUG}",
        )
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        n = seed_db(db)
        print(f"seeded {n} balance-scale puzzles")
    finally:
        db.close()
