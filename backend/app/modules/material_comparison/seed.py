"""Seed/demo puzzles for Heavier Side (real board positions).

Run:  python -m app.modules.material_comparison.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified (valid FEN, 10% difficulty gate,
expected white/black/equal distribution) before insert; invalid entries
fail loudly instead of seeding a broken puzzle. Validation itself always
recomputes material from the stored FEN.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.material_comparison import material as mat
from app.modules.material_comparison.generator import PROMPT_FA, ensure_exercise
from app.modules.material_comparison.validator import SLUG
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle

# Each entry: fen, expected choice, explanation, hints, rating.
# 5 white-ahead / 5 black-ahead / 5 equal, covering pawns, knights,
# bishops, rooks, queens, mixed middlegames, endgames, and the
# kings-only (0 vs 0) edge case. Every FEN below satisfies the 10% gate.
PUZZLES: list[dict] = [
    {
        "fen": "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12",
        "answer": "white",
        "explanation": "سفید جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "ارزش هر مهره را جداگانه حساب کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "rnbq1rk1/pp3ppp/4p3/2ppP3/3P4/2N2N2/PPP2PPP/R1BQ1RK1 w - - 0 7",
        "answer": "white",
        "explanation": "سفید جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌های بزرگ را مقایسه کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "rnbqkbnr/ppp1pppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "answer": "white",
        "explanation": "سفید جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "سربازها را یکی‌یکی بشمار.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1",
        "answer": "white",
        "explanation": "سفید جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "رخ ۵ امتیاز دارد؛ سربازهای اضافه را هم جمع بزن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "3qk3/1p6/8/8/8/8/PP6/3QK3 w - - 0 1",
        "answer": "white",
        "explanation": "سفید جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "وزیر ۹ امتیاز دارد؛ سربازهای هر طرف را جدا جمع بزن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPP1PPPP/RNBQKBNR w KQkq - 0 1",
        "answer": "black",
        "explanation": "سیاه جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "سربازها را یکی‌یکی بشمار.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "r3k3/3ppppp/8/8/8/8/4PPPP/4K1R1 w - - 0 1",
        "answer": "black",
        "explanation": "سیاه جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "رخ ۵ امتیاز دارد؛ سربازهای اضافه را هم جمع بزن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "3qk3/pp6/8/8/8/8/P7/3QK3 w - - 0 1",
        "answer": "black",
        "explanation": "سیاه جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "وزیر ۹ امتیاز دارد؛ سربازهای هر طرف را جدا جمع بزن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "r4rk1/pp3ppp/2nb1n2/3p4/3Pp3/2P1P3/PP1N1PPP/R1B2RK1 w - - 0 1",
        "answer": "black",
        "explanation": "سیاه جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌های بزرگ را مقایسه کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "r1bq1rk1/ppp2ppp/2n2n2/3p4/2PPp3/4P3/PP3PPP/RNBQ1RK1 w - - 0 1",
        "answer": "black",
        "explanation": "سیاه جلوتر بود.",
        "hints": [{"id": "h1", "text_fa": "ارزش هر مهره را جداگانه حساب کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "answer": "equal",
        "explanation": "مهره‌ها مساوی بودند.",
        "hints": [{"id": "h1", "text_fa": "اگر جمع هر دو طرف یکی شد، جواب مساوی است.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "r1bqk2r/ppp2ppp/2p1p3/3p4/2PP4/2P1P3/PP3PPP/R1BQK2R w KQkq - 0 1",
        "answer": "equal",
        "explanation": "مهره‌ها مساوی بودند.",
        "hints": [{"id": "h1", "text_fa": "اسب و فیل هر دو ۳ امتیاز دارند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
        "answer": "equal",
        "explanation": "مهره‌ها مساوی بودند.",
        "hints": [{"id": "h1", "text_fa": "شاه صفر امتیاز دارد.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "answer": "equal",
        "explanation": "مهره‌ها مساوی بودند.",
        "hints": [{"id": "h1", "text_fa": "دو وزیر روبه‌رو هم ارزش یکسانی دارند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1",
        "answer": "equal",
        "explanation": "مهره‌ها مساوی بودند.",
        "hints": [{"id": "h1", "text_fa": "آخرش فقط سربازها مانده‌اند؛ بشمار.", "rating_cost": 5}],
        "rating": 850.0,
    },
]


def verify_puzzle(item: dict) -> str:
    """Independently verify one puzzle definition; return its expected answer.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses raw python-chess totals, never the
    validator or the material module under test.
    """
    import chess

    fen = item.get("fen")
    if not isinstance(fen, str) or not positions.is_valid_fen(fen):
        raise ValueError(f"puzzle needs a valid FEN: {item}")
    board = chess.Board(fen)
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    white = sum(values[p.piece_type] for p in board.piece_map().values() if p.color == chess.WHITE)
    black = sum(values[p.piece_type] for p in board.piece_map().values() if p.color == chess.BLACK)
    larger = max(white, black)
    if larger != 0 and abs(white - black) / larger > 0.10:
        raise ValueError(f"puzzle fails the 10% gate ({white} vs {black}): {fen}")
    expected = "white" if white > black else "black" if black > white else "equal"
    if expected != item.get("answer"):
        raise ValueError(f"classification mismatch: {fen} computed {expected}")
    return expected


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    distribution: dict[str, int] = {}
    for item in PUZZLES:
        expected = verify_puzzle(item)
        distribution[expected] = distribution.get(expected, 0) + 1
    if distribution.get("equal", 0) < 2 or distribution.get("white", 0) < 2 or distribution.get("black", 0) < 2:
        raise ValueError(f"answer distribution not sensible: {distribution}")

    ensure_exercise(db)
    exercise = db.get(Exercise, SLUG)
    assert exercise is not None

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        white, black = mat.material_from_fen(item["fen"])
        _ = (white, black)
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={"fen": item["fen"], "mode": "standard"},
            answer_json={"fen": item["fen"]},
            hint_json={"hints": item["hints"]},
            prompt_fa=PROMPT_FA,
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
        print(f"seeded {n} heavier-side puzzles")
    finally:
        db.close()
