"""Pathfinding puzzle generator (Exercise 6, simple version).

Every puzzle: exactly one white piece (knight 50% / bishop 20% / rook
20% / queen 10%, deliberately weighted — never assumed to emerge), one
distinct star square, empty board otherwise. No king, no pawns, no black
pieces, no second white piece.

- Piece choice uses the documented weights via ``rng.choices`` (finite
  samples fluctuate; batch-exactness is never required).
- Start and target are uniform random distinct squares; the target must
  be REACHABLE (bishop opposite-color pairs are rejected) and its BFS
  ``optimal_moves`` is stored server-side in ``answer_json``.
- Difficulty: uniform sampling already mixes 1-move (rook/queen sharing
  a line, bishop on its diagonal) with natural multi-move knight/bishop
  puzzles. To avoid floods of trivial one-movers, sampling rejects a
  1-move candidate with probability ``AVOID_TRIVIAL`` (bounded retries),
  so the dataset keeps 1-, 2-, 3- and longer puzzles. No adaptive
  difficulty yet.
- The frontend renders from ``Puzzle.fen`` + ``position_json`` (from,
  target, piece) and NEVER receives ``optimal_moves``.

Persisted row: ``fen`` (empty board + piece), ``position_json`` (public),
``answer_json`` (server-only incl. optimal_moves), Persian prompt/hints.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.pathfinding import moves
from app.modules.pathfinding.validator import SLUG
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "مهره را با حرکت‌های قانونی به خانه ستاره‌دار برسان."

HINTS: dict[str, str] = {
    "knight": "اسب به شکل L می‌پرد؛ گاهی دور زدن کوتاه‌تر است.",
    "bishop": "فیل فقط روی قطر هم‌رنگ خودش حرکت می‌کند.",
    "rook": "رخ در ستون و ردیف خالی مستقیم می‌رود.",
    "queen": "وزیر هم مثل رخ و هم مثل فیل حرکت می‌کند.",
}

# Roadmap position: Exercise 6 (Pathfinding; Get Out of Check postponed,
# Pathfinding with Obstacles lands separately as Exercise 7).
SORT_ORDER = 6

TITLE_FA = "مسیر یابی"

# Chance of re-rolling a 1-move candidate to keep longer puzzles common.
AVOID_TRIVIAL = 0.6
MAX_ROLLS = 30


def _random_square(rng: random.Random) -> str:
    return f"{'abcdefgh'[rng.randrange(8)]}{rng.randrange(1, 9)}"


def _fen_for(kind: str, square: str) -> str:
    """Empty-board FEN with the single white piece on ``square``."""
    letter = moves.PIECE_LETTER[kind]
    file_idx = "abcdefgh".index(square[0])
    rank = int(square[1:])
    rows: list[str] = []
    for r in range(8, 0, -1):
        if r == rank:
            left, right = file_idx, 7 - file_idx
            row = ""
            if left:
                row += str(left)
            row += letter
            if right:
                row += str(right)
            rows.append(row)
        else:
            rows.append("8")
    return f"{'/'.join(rows)} w - - 0 1"


def pick_kind(rng: random.Random) -> str:
    kinds = list(moves.PIECE_WEIGHTS.keys())
    weights = [moves.PIECE_WEIGHTS[k] for k in kinds]
    return rng.choices(kinds, weights=weights, k=1)[0]


def generate_question_data(rng: random.Random | None = None) -> dict:
    """Pure question/answer builder (no DB). Always reachable, never trivial-only."""
    rng = rng if rng is not None else random
    for _ in range(MAX_ROLLS):
        kind = pick_kind(rng)
        start = _random_square(rng)
        target = _random_square(rng)
        if target == start:
            continue
        optimal = moves.shortest_path_length(kind, start, target)
        if optimal is None or optimal < 1:
            continue  # unreachable (bishop opposite color) or degenerate
        if optimal == 1 and rng.random() < AVOID_TRIVIAL:
            continue  # keep 1-movers a minority
        return {
            "fen": _fen_for(kind, start),
            "from": start,
            "target": target,
            "piece": kind,
            "optimal_moves": optimal,
            "prompt_fa": PROMPT_FA,
            "explanation": f"کمترین راه {HINTS[kind]}",
            "hint_json": {"hints": [{"id": "h1", "text_fa": HINTS[kind], "rating_cost": 5}]},
        }
    # Bounded fallback: accept the first reachable pair even if trivial.
    for _ in range(MAX_ROLLS):
        kind = pick_kind(rng)
        start = _random_square(rng)
        target = _random_square(rng)
        if target == start:
            continue
        optimal = moves.shortest_path_length(kind, start, target)
        if optimal is not None and optimal >= 1:
            return {
                "fen": _fen_for(kind, start),
                "from": start,
                "target": target,
                "piece": kind,
                "optimal_moves": optimal,
                "prompt_fa": PROMPT_FA,
                "explanation": f"کمترین راه {HINTS[kind]}",
                "hint_json": {"hints": [{"id": "h1", "text_fa": HINTS[kind], "rating_cost": 5}]},
            }
    raise RuntimeError("could not generate a reachable pathfinding puzzle")


def _rating_for(optimal: int, rng: random.Random) -> float:
    return float(max(700.0, min(1250.0, 750.0 + optimal * 60.0 + rng.randrange(0, 50))))


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa=TITLE_FA,
                title_en="Pathfinding",
                description="مهره را با حرکت‌های قانونی به خانه ستاره‌دار برسان.",
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


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one random reachable puzzle and persist it published."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng)
    # Reuse identical (piece, from, target) rows instead of duplicating;
    # steer away from just-shown ids with bounded re-rolls (best-effort).
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
        position_json={"from": data["from"], "target": data["target"], "piece": data["piece"]},
        answer_json={
            "fen": data["fen"],
            "from": data["from"],
            "target": data["target"],
            "piece": data["piece"],
            "optimal_moves": data["optimal_moves"],
        },
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["optimal_moves"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
