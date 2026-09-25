"""Balance Scale puzzle generator (Exercise 9, ترازو).

Every puzzle: 4–10 random black pieces on the left pan (pawn/knight/
bishop/rook/queen — never a king). The user must match the total with
at most 10 white pieces; the fewest pieces score highest.

Generate → solve → validate → accept:
1. Random piece count in [4, 10] and random composition.
2. Recompute the target and the DP optimal count server-side.
3. Accept only when the target is solvable within 10 pieces
   (``optimal_count <= 10``) and the distribution guard passes.

Distribution: uniform sampling alone clusters around medium targets and
over-produces trivial 1-piece optimals, so generation mixes three tiers
(low 4–15 / medium 16–35 / high 36–90) and throttles optimal==1 puzzles.
This yields low/medium/high targets, easy and multi-piece solutions,
heavy-piece-optimal and light-piece-optimal cases, and targets with
multiple equally optimal solutions (e.g. 10 = 9+1 or 5+5).

Persisted row: ``fen`` stays NULL (no board for this exercise),
``position_json`` carries only the public left pieces, ``answer_json``
carries left + derived target/optimal (server-only; the puzzle endpoints
never expose ``answer_json``).
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.balance_scale import solver
from app.modules.balance_scale.solver import MAX_PIECES
from app.modules.balance_scale.validator import SLUG, normalize_piece, total_value
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_GENERATED, Puzzle
from app.modules.puzzles.service import reusable_candidate_query, stage_validated_puzzle

PROMPT_FA = "با کمترین مهره، کفه سفید را با کفه سیاه برابر کن."

# Catalog display order: unchanged from the previous prototype (8) so the
# existing exercise list is not renumbered by this rewrite.
SORT_ORDER = 8

TITLE_FA = "ترازو"
TITLE_EN = "Balance Scale"
DESCRIPTION_FA = "با کمترین مهره سفید، کفه را با مهره‌های سیاه برابر کن."

# Piece pool with weights: pawns slightly common (they create interesting
# light-piece optimals), queens slightly rare (they trivialize targets).
PIECE_POOL = ["p", "p", "n", "b", "r", "q"]
MIN_LEFT_PIECES = 4

# Chance of re-rolling a 1-piece-optimal candidate to keep trivial
# single-piece puzzles a minority.
AVOID_TRIVIAL = 0.7
MAX_ROLLS = 60


def _random_left(rng: random.Random) -> list[str]:
    count = rng.randint(MIN_LEFT_PIECES, MAX_PIECES)
    return [rng.choice(PIECE_POOL) for _ in range(count)]


def _tier_of(target: int) -> str:
    if target <= 15:
        return "low"
    if target <= 35:
        return "medium"
    return "high"


def generate_question_data(rng: random.Random | None = None) -> dict:
    """Pure question/answer builder (no DB). Validated, never trivial-only."""
    rng = rng if rng is not None else random
    fallback: dict | None = None
    for _ in range(MAX_ROLLS):
        tier = rng.choice(["low", "medium", "high"])
        left = _random_left(rng)
        clean = [p for p in (normalize_piece(p) for p in left) if p is not None]
        if len(clean) != len(left):
            continue  # pragma: no cover - pool only holds valid pieces
        target = total_value(clean)
        if _tier_of(target) != tier:
            continue
        optimal = solver.optimal_count(target)
        if optimal is None or optimal > MAX_PIECES:
            continue  # not matchable within the 10-slot right pan
        if optimal == 1 and rng.random() < AVOID_TRIVIAL:
            if fallback is None:
                fallback = {"left": left, "target": target, "optimal_count": optimal}
            continue  # keep 1-piece solutions a minority
        return {"left": left, "target": target, "optimal_count": optimal}
    if fallback is not None:
        return fallback
    # Bounded fallback: any solvable composition (never trivial-only by
    # construction only when the loop above found nothing, e.g. odd RNG).
    for _ in range(MAX_ROLLS):
        left = _random_left(rng)
        target = total_value([p for p in (normalize_piece(p) for p in left) if p is not None])
        optimal = solver.optimal_count(target)
        if optimal is not None and optimal <= MAX_PIECES:
            return {"left": left, "target": target, "optimal_count": optimal}
    raise RuntimeError("could not generate a solvable balance-scale puzzle")


def _rating_for(target: int, optimal: int, rng: random.Random) -> float:
    return float(max(700.0, min(1350.0, 750.0 + target * 6.0 + optimal * 10.0 + rng.randrange(0, 30))))


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa=TITLE_FA,
                title_en=TITLE_EN,
                description=DESCRIPTION_FA,
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
        if exercise.title_fa != TITLE_FA:
            exercise.title_fa = TITLE_FA
            changed = True
        if exercise.title_en != TITLE_EN:
            exercise.title_en = TITLE_EN
            changed = True
        if changed:
            db.commit()


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
    *,
    source: str = SOURCE_GENERATED,
    source_reference: str | None = None,
) -> Puzzle:
    """Generate one random validated puzzle and stage it as a candidate."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng)
    # Reuse identical left-composition rows instead of duplicating; steer
    # away from just-shown ids with bounded re-rolls (best-effort).
    # Filtered in Python (portable across SQLite/PostgreSQL, tiny tables).
    for _ in range(10):
        candidates = reusable_candidate_query(db, SLUG).order_by(Puzzle.id).all()
        usable: Puzzle | None = None
        identical = False
        for puzzle in candidates:
            pos = puzzle.position_json if isinstance(puzzle.position_json, dict) else {}
            if sorted(str(p).upper() for p in (pos.get("left") or [])) == sorted(
                str(p).upper() for p in data["left"]
            ):
                identical = True
                if usable is None and puzzle.id not in excluded:
                    usable = puzzle
        if usable is not None:
            return usable
        if not identical:
            break
        data = generate_question_data(rng)
    puzzle = stage_validated_puzzle(
        db,
        {
            "exercise_slug": SLUG,
            "fen": None,
            "position_json": {"left": data["left"]},
            "answer_json": {
                "left": data["left"],
                "target": data["target"],
                "optimal_count": data["optimal_count"],
            },
            "hint_json": {
                "hints": [
                    {"id": "h1", "text_fa": "اول ارزش همه مهره‌های سیاه را جمع بزن.", "rating_cost": 5},
                ]
            },
            "prompt_fa": PROMPT_FA,
            "explanation": f"مجموع کفه سیاه {data['target']} است؛ با کمترین مهره به همین عدد برس.",
            "initial_rating": _rating_for(data["target"], data["optimal_count"], rng),
        },
        source=source,
        source_reference=source_reference
        or (f"generator:{SLUG}" if source == SOURCE_GENERATED else f"{source}:{SLUG}"),
    )
    db.commit()
    db.refresh(puzzle)
    return puzzle
