"""Seed/demo puzzles for Blindfold Calculation (best move, eyes closed).

Run:  python -m app.modules.blindfold_calculation.seed
Idempotent: skips when current-shape puzzles for the slug already exist.

Every entry is a REAL Lichess puzzle row (PuzzleId/FEN/Rating from the
shared ``puzzles.db``): the authoritative answer is the FIRST move of
that puzzle's curated line, never invented and never engine-derived.
Each entry is independently verified before insert (valid FEN, at most
12 pieces, first move legal) and fails loudly otherwise.

Security: the FEN lives ONLY in server-side answer_json. The Puzzle.fen
column stays NULL and position_json carries just the Persian
description, side to move, mode and piece count -- so the normal puzzle
endpoint never leaks the position or the expected move before
submission. The explanation stays generic (no squares) for the same
reason.

Migration: legacy mate-in-1 rows (answer_json with "example"/"mate_count"
and no "solution") are archived, never hard-deleted, before the new
rows go in.
"""

import chess
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.blindfold_calculation.description import describe_position, piece_count, side_to_move
from app.modules.blindfold_calculation.generator import (
    EXPLANATION_FA,
    HINTS,
    MAX_PIECES,
    PROMPT_FA,
    ensure_exercise,
)
from app.modules.blindfold_calculation.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import archive, stage_validated_puzzle

# Each entry: real puzzles.db row (puzzle_id, fen, rating) + the first
# move of its curated solution line. 8 White to move / 7 Black to move,
# covering captures, promotions, king moves, checks and quiet moves.
PUZZLES: list[dict] = [
    {"puzzle_id": "gjy0e", "fen": "3k4/p7/2K5/3P2p1/1P3p2/P7/6P1/8 w - - 0 39", "rating": 1166, "solution": "c6d6"},
    {"puzzle_id": "ix2gC", "fen": "8/3k4/1P2n3/1K6/8/8/6p1/6N1 w - - 3 58", "rating": 918, "solution": "g1f3"},
    {"puzzle_id": "akJ2a", "fen": "R7/6pk/7p/4QP2/2q2K2/4P3/5R1P/6r1 w - - 5 51", "rating": 1598, "solution": "e5e4"},
    {"puzzle_id": "cQ7em", "fen": "6R1/5p2/1p2p3/p6Q/4k3/q4r2/P7/K4R2 w - - 6 43", "rating": 1017, "solution": "f1f3"},
    {"puzzle_id": "JkQ8N", "fen": "6R1/4Pkp1/7p/5p2/8/P4PK1/4rP2/8 w - - 3 37", "rating": 957, "solution": "e7e8q"},
    {"puzzle_id": "LlBs9", "fen": "6r1/3RPk2/p7/1p6/8/P6Q/P4PK1/1q6 w - - 3 46", "rating": 818, "solution": "g2h2"},
    {"puzzle_id": "RC4Jo", "fen": "6k1/5p1p/3br3/8/Q3n3/6PP/7K/6R1 w - - 3 36", "rating": 1064, "solution": "g1e1"},
    {"puzzle_id": "PtUL1", "fen": "Q7/6qk/2P5/2Q5/2N1p1b1/4P3/6K1/8 w - - 1 44", "rating": 1283, "solution": "a8f8"},
    {"puzzle_id": "j9Heu", "fen": "5rk1/5pp1/8/3NQ2p/8/6PP/5q2/7K b - - 1 31", "rating": 1040, "solution": "h5h4"},
    {"puzzle_id": "wCR9X", "fen": "8/1k3Q2/1p6/p2p4/PP2q3/2P5/K7/8 b - - 2 55", "rating": 1065, "solution": "b7a6"},
    {"puzzle_id": "sxtQA", "fen": "6k1/6p1/6P1/4pP2/4P2p/R1K5/1r1p4/8 b - - 0 48", "rating": 653, "solution": "d2d1q"},
    {"puzzle_id": "GldPU", "fen": "8/1pp4n/6p1/1P2p1k1/2P3P1/2B3K1/8/8 b - - 2 50", "rating": 1516, "solution": "h7f6"},
    {"puzzle_id": "gQ0JG", "fen": "5k2/p5p1/2P4p/4N3/7P/2r3P1/7K/8 b - - 0 39", "rating": 1433, "solution": "c3c5"},
    {"puzzle_id": "qo7hw", "fen": "5k2/5pp1/1N5p/8/2P2KP1/2r4P/8/8 b - - 0 46", "rating": 895, "solution": "f8e7"},
    {"puzzle_id": "S4Oa8", "fen": "8/8/4R3/7k/p4P2/3pp1K1/r5P1/8 b - - 1 45", "rating": 2071, "solution": "e3e2"},
]


def verify_puzzle(item: dict) -> str:
    """Fail loudly unless the row is eligible; return its canonical SAN."""
    fen = item.get("fen")
    solution = item.get("solution")
    if not isinstance(fen, str) or not isinstance(solution, str):
        raise ValueError(f"puzzle needs a FEN and a solution UCI: {item}")
    board = chess.Board(fen)  # raises on invalid FEN
    count = piece_count(fen)
    if count > MAX_PIECES:
        raise ValueError(f"expected at most {MAX_PIECES} pieces, got {count}: {fen}")
    move = chess.Move.from_uci(solution)
    if move not in board.legal_moves:
        raise ValueError(f"solution {solution} illegal in {fen}")
    # Description must generate without errors (blindfold suitability).
    describe_position(fen)
    return board.san(move)


def _archive_legacy_rows(db: Session) -> int:
    """Archive mate-in-1 prototype rows (no stored solution). Never deletes."""
    rows = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    archived = 0
    for row in rows:
        answer = row.answer_json if isinstance(row.answer_json, dict) else {}
        if not answer.get("solution") and not row.is_archived:
            archive(db, row)
            archived += 1
    return archived


def seed_db(db: Session) -> int:
    """Archive legacy rows, then insert exercise + puzzles. Returns created count."""
    for item in PUZZLES:
        verify_puzzle(item)

    ensure_exercise(db)
    exercise = db.get(Exercise, SLUG)
    assert exercise is not None

    _archive_legacy_rows(db)

    existing = (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == SLUG,
            Puzzle.is_archived == False,  # noqa: E712
        )
        .count()
    )
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        san = verify_puzzle(item)
        _ = san
        count = piece_count(item["fen"])
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": None,
                "position_json": {
                    "description_fa": describe_position(item["fen"]),
                    "side_to_move": side_to_move(item["fen"]),
                    "mode": "best-move",
                    "piece_count": count,
                },
                "answer_json": {
                    "fen": item["fen"],
                    "solution": item["solution"],
                    "puzzle_id": item["puzzle_id"],
                    "rating": float(item["rating"]),
                },
                "hint_json": {"hints": HINTS},
                "prompt_fa": PROMPT_FA,
                "explanation": EXPLANATION_FA,
                "initial_rating": float(item["rating"]),
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
        print(f"seeded {n} blindfold-calculation puzzles")
    finally:
        db.close()
