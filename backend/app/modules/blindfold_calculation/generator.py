"""Blindfold Calculation question generator: real positions, one best move.

Every puzzle comes from the shared ``puzzles.db`` (full Lichess rows via
``positions.repository.fetch_random_puzzle_row``). The FEN is the
position; the authoritative answer is the FIRST move of that puzzle's
curated Lichess line — the database is authoritative, nothing is
invented and no engine replaces it.

Eligibility (bounded, never an infinite loop):

1. ``piece_count(fen) <= MAX_PIECES`` (12) so the verbal description
   stays reconstructible without a board.
2. The stored line is non-empty and its first UCI parses AND is legal in
   the stored FEN (corrupt rows are skipped, never served).
3. Uniqueness is the Lichess curation invariant: each puzzle row exists
   precisely because its first move is the single best move, so grading
   exactly that move is deterministic. No extra engine check is added.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` validates against the stored ``answer_json``).
The FEN never leaves the server: ``Puzzle.fen`` stays NULL and
``position_json`` carries only the Persian description, side to move,
mode and piece count. Identical puzzle rows are reused, not duplicated;
``exclude_ids`` steers away from just-shown puzzles (bounded re-roll;
best-effort). When ``puzzles.db`` is missing, curated fallback rows
(from the seed module, verified the same way) keep the exercise
playable.
"""

from __future__ import annotations

import random

import chess
from sqlalchemy.orm import Session

from app.modules.blindfold_calculation.description import (
    describe_position,
    piece_count,
    side_to_move,
)
from app.modules.blindfold_calculation.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "بهترین حرکت چیست؟"

EXPLANATION_FA = "بهترین حرکت همین بود. جای مهره‌ها را در ذهنت مرور کن و ببین چرا این حرکت بهتر است."

HINTS = [
    {"id": "h1", "text_fa": "اول جای شاه هر دو طرف و خانه‌های اطرافشان را در ذهنت پیدا کن.", "rating_cost": 5},
    {"id": "h2", "text_fa": "کیش‌ها، زدن‌ها و حرکت‌هایی که مهره بی‌دفاع را نجات می‌دهند را یکی‌یکی بررسی کن.", "rating_cost": 10},
]

# Maximum pieces on the board: the description must stay mentally
# reconstructible, so larger positions are never candidates.
MAX_PIECES = 12

# Bounded random-selection loop (never infinite). Small (<=12-piece)
# endgames are ~15% of real puzzle rows, so 60 probes almost always hit.
MAX_CANDIDATES = 60


def question_for_row(puzzle_id: str, fen: str, rating: int, moves: list[str]) -> dict | None:
    """Pure question/answer builder for one puzzles.db row (no DB, no random).

    Returns None when the row is ineligible (too many pieces, empty line,
    or a first move that is not legal in the FEN).
    """
    if not positions.is_valid_fen(fen):
        return None
    try:
        count = piece_count(fen)
    except ValueError:
        return None
    if count > MAX_PIECES:
        return None
    if not moves:
        return None
    solution = moves[0]
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(solution)
        if move not in board.legal_moves:
            return None
        solution_san = board.san(move)
    except (ValueError, AssertionError):
        return None
    return {
        "puzzle_id": puzzle_id,
        "fen": fen,
        "solution": solution,
        "solution_san": solution_san,
        "piece_count": count,
        "side": side_to_move(fen),
        "description_fa": describe_position(fen),
        "rating": float(rating) if isinstance(rating, (int, float)) else 1200.0,
    }


def generate_question_data(
    rng: random.Random | None = None,
    explicit_path: str | None = None,
) -> dict:
    """Pick a random eligible position from puzzles.db (or curated fallback)."""
    rng = rng if rng is not None else random
    path = positions.resolve_source_path(explicit_path)
    if path is not None:
        for _ in range(MAX_CANDIDATES):
            row = positions.fetch_random_puzzle_row(path, rng)
            if row is None:
                continue
            data = question_for_row(row["puzzle_id"], row["fen"], row["rating"], row["moves"])
            if data is not None:
                return data
    # Fallback (puzzles.db missing or unusable): curated rows verified the
    # same way. Never crashes; the exercise stays playable offline.
    from app.modules.blindfold_calculation import seed as seed_mod

    candidates = list(seed_mod.PUZZLES)
    rng.shuffle(candidates)
    for item in candidates:
        data = question_for_row(
            item["puzzle_id"], item["fen"], item["rating"], [item["solution"]]
        )
        if data is not None:
            return data
    raise RuntimeError("could not generate an eligible blindfold-calculation puzzle")


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="محاسبه‌ی ذهنی",
                title_en="Blindfold Calculation",
                description="بدون دیدن صفحه، بهترین حرکت را پیدا کن.",
                is_active=True,
                sort_order=14,
            )
        )
        db.commit()
    else:
        changed = False
        if exercise.title_fa != "محاسبه‌ی ذهنی":
            exercise.title_fa = "محاسبه‌ی ذهنی"
            changed = True
        if exercise.title_en != "Blindfold Calculation":
            exercise.title_en = "Blindfold Calculation"
            changed = True
        if exercise.description != "بدون دیدن صفحه، بهترین حرکت را پیدا کن.":
            exercise.description = "بدون دیدن صفحه، بهترین حرکت را پیدا کن."
            changed = True
        if changed:
            db.commit()


def _match_existing(db: Session, puzzle_id: str, exclude_ids: set[int]) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists) for a puzzles.db puzzle_id."""
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
        answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
        if answer.get("solution") and answer.get("puzzle_id") == puzzle_id:
            identical = True
            if usable is None and puzzle.id not in exclude_ids:
                usable = puzzle
    return usable, identical


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    explicit_path: str | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one random eligible question and persist it published."""
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, explicit_path)
    usable, identical = _match_existing(db, data["puzzle_id"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, explicit_path)
            usable, identical = _match_existing(db, data["puzzle_id"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=None,
        position_json={
            "description_fa": data["description_fa"],
            "side_to_move": data["side"],
            "mode": "best-move",
            "piece_count": data["piece_count"],
        },
        answer_json={
            "fen": data["fen"],
            "solution": data["solution"],
            "puzzle_id": data["puzzle_id"],
            "rating": data["rating"],
        },
        hint_json={"hints": HINTS},
        prompt_fa=PROMPT_FA,
        explanation=EXPLANATION_FA,
        initial_rating=data["rating"],
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
