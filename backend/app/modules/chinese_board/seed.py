"""Seed/demo puzzles for Chinese Board (realistic positions, rising size).

Run:  python -m app.modules.chinese_board.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified (valid FEN, piece count and study
budget recomputed from the FEN, sensible size spread) before insert;
invalid entries fail loudly instead of seeding a broken puzzle.
Validation itself always recomputes the piece set from the stored FEN.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.chinese_board import pieces as cb
from app.modules.chinese_board.generator import PROMPT_FA, ensure_exercise
from app.modules.chinese_board.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.positions import repository as positions
from app.modules.puzzles.models import Puzzle

# Each entry: fen + hints + rating. 15 positions from tiny (4 pieces) to
# full (32 pieces) so the study budget (count * 1000ms) is exercised across
# its whole natural range. Explanations are generated from the FEN.
PUZZLES: list[dict] = [
    {
        "fen": "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "فقط چهار مهره است؛ جای هر کدام را جدا حفظ کن.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/5PPP/4K2R w K - 0 1",
        "hints": [{"id": "h1", "text_fa": "اول شاه‌ها، بعد رخ و سربازها.", "rating_cost": 5}],
        "rating": 720.0,
    },
    {
        "fen": "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "سربازها را ستون‌به‌ستون حفظ کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "آخرش فقط شاه و سرباز مانده‌اند.", "rating_cost": 5}],
        "rating": 780.0,
    },
    {
        "fen": "4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "رخ‌ها را اول پیدا کن، بعد سربازها.", "rating_cost": 5}],
        "rating": 820.0,
    },
    {
        "fen": "3qk3/1p6/8/8/8/8/PP6/3QK3 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "وزیرها مهم‌ترین مهره‌ها هستند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "r4rk1/pp3ppp/2nb1n2/3p4/3Pp3/2P1P3/PP1N1PPP/R1B2RK1 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "مهره‌های بزرگ را اول، سربازها را بعد.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "rnb1kbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        "hints": [{"id": "h1", "text_fa": "کدام خانه‌ها خالی شده‌اند؟", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 1",
        "hints": [{"id": "h1", "text_fa": "فقط چند مهره جابه‌جا شده‌اند.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 1",
        "hints": [{"id": "h1", "text_fa": "مهره‌ها را دسته‌دسته حفظ کن.", "rating_cost": 5}],
        "rating": 1000.0,
    },
    {
        "fen": "r1bqk2r/ppp2ppp/2p1p3/3p4/2PP4/2P1P3/PP3PPP/R1BQK2R w KQkq - 0 1",
        "hints": [{"id": "h1", "text_fa": "اول شاه‌ها، بعد مهره‌های بزرگ، بعد سربازها.", "rating_cost": 5}],
        "rating": 1050.0,
    },
    {
        "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "hints": [{"id": "h1", "text_fa": "اسب‌ها و فیل‌ها را جفت‌جفت حفظ کن.", "rating_cost": 5}],
        "rating": 1100.0,
    },
    {
        "fen": "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12",
        "hints": [{"id": "h1", "text_fa": "وسط صفحه را با دقت نگاه کن.", "rating_cost": 5}],
        "rating": 1150.0,
    },
    {
        "fen": "r1bq1rk1/ppp2ppp/2n2n2/3p4/2PPp3/4P3/PP3PPP/RNBQ1RK1 w - - 0 1",
        "hints": [{"id": "h1", "text_fa": "پیاده رونده را فراموش نکن.", "rating_cost": 5}],
        "rating": 1150.0,
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "hints": [{"id": "h1", "text_fa": "وضعیت شروع بازی؛ جای همه مهره‌ها سر جایشان است.", "rating_cost": 5}],
        "rating": 1200.0,
    },
]


def verify_puzzle(item: dict) -> int:
    """Independently verify one puzzle definition; return its piece count.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses raw python-chess, never the helpers
    under test.
    """
    import chess

    fen = item.get("fen")
    if not isinstance(fen, str) or not positions.is_valid_fen(fen):
        raise ValueError(f"puzzle needs a valid FEN: {item}")
    board = chess.Board(fen)
    count = len(board.piece_map())
    if count < 2:
        raise ValueError(f"puzzle needs at least the two kings: {fen}")
    kings = sum(1 for p in board.piece_map().values() if p.piece_type == chess.KING)
    if kings != 2:
        raise ValueError(f"puzzle needs exactly two kings: {fen}")
    return count


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    counts = [verify_puzzle(item) for item in PUZZLES]
    if min(counts) > 8 or max(counts) < 24:
        raise ValueError(f"seed must span tiny to full positions: {sorted(counts)}")

    ensure_exercise(db)
    exercise = db.get(Exercise, SLUG)
    assert exercise is not None

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item, count in zip(PUZZLES, counts):
        budget = count * cb.MEMORIZE_MS_PER_PIECE
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={
                "fen": item["fen"],
                "piece_count": count,
                "memorization_ms": budget,
                "mode": "standard",
            },
            answer_json={"fen": item["fen"]},
            hint_json={"hints": item["hints"]},
            prompt_fa=PROMPT_FA,
            explanation=f"این صفحه {count} مهره داشت.",
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
        print(f"seeded {n} chinese-board puzzles")
    finally:
        db.close()
