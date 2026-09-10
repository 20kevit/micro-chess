"""Pathfinding-with-obstacles puzzle generator (Exercise 7).

Every puzzle: exactly one white mover (knight/bishop/rook/queen), one or
more black enemies (pawn/knight/bishop/rook/queen), one distinct empty
star square. No kings at all, no second white piece, no white pawn/king,
no black king.

Workflow per candidate: generate -> check board constraints -> run the
BFS solver over complete states -> check quality gates -> accept/reject.
A puzzle is NEVER served without an explicitly verified solution.

Quality gates (documented thresholds, tuned by practical testing):
- ``MIN_ENEMIES = 1`` / ``MAX_ENEMIES = 5``: enough material for
  blocking/control/capture play, few enough to keep the state space
  (white square x remaining-enemy subsets) small.
- ``MIN_OPTIMAL = 2`` / ``MAX_OPTIMAL = 10``: rejects trivial one-movers
  and overlong tours (60s speed sessions need snappy puzzles).
- ``MAX_SOLVER_VISITED = 20000``: rejects positions whose state space is
  unnecessarily huge (solver must also stay within its own cap).
- Meaningfulness: the obstacles must actually matter. Accept when the
  optimal route captures at least once OR the obstacle optimum is longer
  than the empty-board distance for the same (piece, from, target).
  This rejects positions that play identically to a trivial Exercise 6
  puzzle.
- Bishop color bound: a bishop can never change square color (captures
  land on same-color squares too), so opposite-color (from, target) pairs
  are rejected up front via the empty-board baseline.

Persisted row: ``fen`` (full position, for rendering),
``position_json`` (public task data: from/target/piece/enemies),
``answer_json`` (server-only: task data + ``optimal_moves``).
Identical enemy configurations are reused, not duplicated;
``exclude_ids`` steers variety with bounded re-rolls.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.pathfinding_obstacles import transitions as tr
from app.modules.pathfinding_obstacles.validator import SLUG
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "مهره را با کمترین حرکت به ستاره برسانید."

HINTS: dict[str, str] = {
    "knight": "اسب از روی مهره‌ها می‌پرد، ولی فقط روی خانه امن می‌تواند بنشیند.",
    "bishop": "فیل از روی مهره رد نمی‌شود؛ مهره بی‌دفاع را می‌توان زد.",
    "rook": "رخ از روی مهره رد نمی‌شود؛ خانه زیر ضربه دشمن امن نیست.",
    "queen": "وزیر هم مثل رخ و هم مثل فیل حرکت می‌کند؛ مقصد باید امن باشد.",
}

# Roadmap position: Exercise 8 (direct evolution of Exercise 7 مسیریابی).
SORT_ORDER = 7

TITLE_FA = "مسیریابی با مانع"

# Same piece-target mix as Exercise 7 (continuity, not assumed).
PIECE_WEIGHTS: dict[str, float] = {
    "knight": 0.50,
    "bishop": 0.20,
    "rook": 0.20,
    "queen": 0.10,
}

MIN_ENEMIES = 1
MAX_ENEMIES = 5
MIN_OPTIMAL = 2
MAX_OPTIMAL = 10
# Solver-visited ceiling for served puzzles (below transitions.MAX_VISITED).
MAX_SOLVER_VISITED = 20000

MAX_CANDIDATES = 200

_FILES = "abcdefgh"


def _random_square(rng: random.Random) -> str:
    return f"{_FILES[rng.randrange(8)]}{rng.randrange(1, 9)}"


def pick_kind(rng: random.Random) -> str:
    kinds = list(PIECE_WEIGHTS.keys())
    weights = [PIECE_WEIGHTS[k] for k in kinds]
    return rng.choices(kinds, weights=weights, k=1)[0]


def _random_enemy_kind(rng: random.Random, square: str) -> str:
    kind = rng.choice(list(tr.ALLOWED_ENEMY_KINDS))
    if kind == "pawn" and square[1] in ("1", "8"):
        # Pawns on the first/last rank never occur in real games and have
        # degenerate attack geometry; keep positions teachable.
        kind = rng.choice(["knight", "bishop", "rook", "queen"])
    return kind


def _random_enemies(rng: random.Random, forbidden: set[str]) -> list[tuple[str, str]]:
    count = rng.randint(MIN_ENEMIES, MAX_ENEMIES)
    enemies: list[tuple[str, str]] = []
    used = set(forbidden)
    for _ in range(count):
        for _ in range(100):
            sq = _random_square(rng)
            if sq not in used:
                break
        else:
            break
        used.add(sq)
        enemies.append((sq, _random_enemy_kind(rng, sq)))
    enemies.sort()
    return enemies


def _try_kind(rng: random.Random, kind: str) -> dict | None:
    """Build one accepted puzzle for a fixed kind, or None."""
    for _ in range(MAX_CANDIDATES // 4):
        start = _random_square(rng)
        target = _random_square(rng)
        if target == start:
            continue
        # Bishop color bound: no capture can change it.
        baseline = tr.empty_board_distance(kind, start, target)
        if baseline is None:
            continue
        enemies = _random_enemies(rng, {start, target})
        if len(enemies) < MIN_ENEMIES:
            continue
        try:
            state = tr.State(
                white_kind=kind,
                white_square=start,
                enemies=tuple(enemies),
                target=target,
            )
        except Exception:
            continue
        solved = tr.solve(state)
        if solved is None:
            continue  # unsolvable (or state space too big): reject
        optimal = solved["optimal_moves"]
        if not (MIN_OPTIMAL <= optimal <= MAX_OPTIMAL):
            continue
        if solved["visited"] > MAX_SOLVER_VISITED:
            continue
        # Meaningfulness: obstacles must change planning (a capture on the
        # optimal route, or a longer optimum than the empty-board baseline).
        if solved["captures"] < 1 and optimal <= baseline:
            continue
        return {
            "fen": tr.fen_for_state(state),
            "from": start,
            "target": target,
            "piece": kind,
            "enemies": [{"square": sq, "kind": k} for sq, k in state.enemies],
            "optimal_moves": optimal,
            "prompt_fa": PROMPT_FA,
            "explanation": f"کمترین راه {HINTS[kind]}",
            "hint_json": {"hints": [{"id": "h1", "text_fa": HINTS[kind], "rating_cost": 5}]},
        }
    return None


def generate_question_data(rng: random.Random | None = None) -> dict:
    """Pure question/answer builder (no DB). Solved + quality-gated.

    Kinds are drawn with the documented weights, but each drawn kind gets
    its own bounded batch of enemy placements: sliders accept random
    placements far less often than knights, and without per-kind retries
    the output would collapse to nearly all knights.
    """
    rng = rng if rng is not None else random
    for _ in range(8):
        data = _try_kind(rng, pick_kind(rng))
        if data is not None:
            return data
    raise RuntimeError("could not generate a solvable obstacle-pathfinding puzzle")


def _rating_for(optimal: int, enemy_count: int, rng: random.Random) -> float:
    base = 800.0 + optimal * 60.0 + enemy_count * 15.0 + rng.randrange(0, 50)
    return float(max(700.0, min(1400.0, base)))


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa=TITLE_FA,
                title_en="Pathfinding with Obstacles",
                description="مهره را با کمترین حرکت، با عبور از موانع، به ستاره برسانید.",
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
        if changed:
            db.commit()


def _same_enemies(a: list, b: list) -> bool:
    normalize = lambda items: sorted(
        (e.get("square"), e.get("kind")) for e in items if isinstance(e, dict)
    )
    return normalize(a) == normalize(b)


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one solved, quality-gated puzzle and persist it published."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng)
    # Reuse identical (piece, from, target, enemies) rows instead of
    # duplicating; steer away from just-shown ids with bounded re-rolls.
    # Filtered in Python (portable across SQLite/PostgreSQL, tiny tables).
    for _ in range(10):
        candidates = (
            db.query(Puzzle)
            .filter(
                Puzzle.exercise_slug == SLUG,
                Puzzle.is_published == True,  # noqa: E712
                Puzzle.is_archived == False,  # noqa: E712
            )
            .order_by(Puzzle.id)
            .all()
        )
        usable: Puzzle | None = None
        identical = False
        for puzzle in candidates:
            pos = puzzle.position_json if isinstance(puzzle.position_json, dict) else {}
            if (
                pos.get("from") == data["from"]
                and pos.get("target") == data["target"]
                and pos.get("piece") == data["piece"]
                and _same_enemies(pos.get("enemies", []), data["enemies"])
            ):
                identical = True
                if usable is None and puzzle.id not in excluded:
                    usable = puzzle
        if usable is not None:
            return usable
        if not identical:
            break
        data = generate_question_data(rng)
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={
            "from": data["from"],
            "target": data["target"],
            "piece": data["piece"],
            "enemies": data["enemies"],
        },
        answer_json={
            "from": data["from"],
            "target": data["target"],
            "piece": data["piece"],
            "enemies": data["enemies"],
            "optimal_moves": data["optimal_moves"],
        },
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["optimal_moves"], len(data["enemies"]), rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
