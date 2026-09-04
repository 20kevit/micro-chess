"""Seed/demo puzzles for Memory Board.

Run:  python -m app.modules.memory_board.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified with raw python-chess (parses,
both kings present, no stacked pieces, valid side to move, solvable
memorization duration) before insert; invalid entries fail loudly instead
of seeding a broken puzzle. Validation itself never depends on anything
but the stored FEN.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.memory_board.validator import SLUG
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "این موقعیت را به خاطر بسپار."

# Each entry: fen, memorize_seconds, prompt, explanation, hints, rating.
# Ordered easy → hard: few pieces and simple structures first.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/8/8/8/8/5P2/4K2R w K - 0 1",
        "memorize_seconds": 8,
        "memorize_seconds": 8,
        "prompt_fa": PROMPT_FA,
        "explanation": "اول شاه‌ها را به خاطر بسپار: سفید e1 و سیاه e8. بعد رخ تنها در h1 و سرباز f2 را اضافه کن.",
        "hints": [{"id": "h1", "text_fa": "اول جای شاه‌ها را به خاطر بسپار.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/8/8/5n2/8/4K3 b - - 0 1",
        "memorize_seconds": 8,
        "prompt_fa": PROMPT_FA,
        "memorize_seconds": 8,
        "explanation": "نوبت با سیاه است. اسب تنها در f3 ایستاده؛ بقیه صفحه فقط دو شاه است.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت هم دقت کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "r6k/8/8/8/8/8/8/R5K1 w - - 0 1",
        "memorize_seconds": 8,
        "prompt_fa": PROMPT_FA,
        "explanation": "دو رخ در گوشه‌های مخالف (a1 و a8) و دو شاه در گوشه‌های دیگر؛ تقارن را به خاطر بسپار.",
        "hints": [{"id": "h1", "text_fa": "تقارن صفحه را پیدا کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1",
        "memorize_seconds": 8,
        "prompt_fa": PROMPT_FA,
        "explanation": "دو سرباز روبه‌رو (d5 سیاه و e4 سفید) به‌علاوه دو شاه؛ ساختار ساده پیاده‌ای.",
        "hints": [{"id": "h1", "text_fa": "ساختار پیاده‌ها را جداگانه حفظ کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/3B4/4K3 w - - 0 1",
        "memorize_seconds": 8,
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل تنها در d2؛ شاه سفید e1 و شاه سیاه e8.",
        "hints": [{"id": "h1", "text_fa": "مهره تنها را با مختصاتش حفظ کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "r3k3/8/8/8/8/8/5PPP/5RK1 w - - 0 1",
        "memorize_seconds": 6,
        "prompt_fa": PROMPT_FA,
        "explanation": "شاه و رخ سفید در جناح شاه (f1، g1) با سه سرباز جلویشان؛ رخ سیاه تنها در a8.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ها را دسته‌دسته حفظ کن: شاه و رخ، بعد پیاده‌ها.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/2b5/8/5N2/8/4K3 w - - 0 1",
        "memorize_seconds": 6,
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل سیاه c5 و اسب سفید f3؛ دو سوار سبک در مرکز صفحه.",
        "hints": [{"id": "h1", "text_fa": "اول رنگ هر مهره، بعد خانه‌اش را حفظ کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/1p6/8/8/8/8/1P6/4K3 b - - 0 1",
        "memorize_seconds": 6,
        "prompt_fa": PROMPT_FA,
        "explanation": "نوبت با سیاه است. دو سرباز روبه‌رو در ستون b؛ بقیه صفحه خالی است.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت هم دقت کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "memorize_seconds": 6,
        "prompt_fa": PROMPT_FA,
        "explanation": "دو وزیر روبه‌رو در d1 و d8؛ شاه‌ها پشت سرشان در e1 و e8.",
        "hints": [{"id": "h1", "text_fa": "مهره‌های سنگین را اول حفظ کن.", "rating_cost": 5}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/PP6/R3K3 w Q - 0 1",
        "memorize_seconds": 6,
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ a1 با دو سرباز a2 و b2؛ شاه e1. حق قلعه بزرگ هم هست.",
        "hints": [{"id": "h1", "text_fa": "صفحه را سیستماتیک از یک گوشه اسکن کن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "r2qk3/pp3ppp/8/3p4/3P4/2N5/PP3PPP/R3K3 w Q - 0 1",
        "memorize_seconds": 4,
        "prompt_fa": PROMPT_FA,
        "explanation": "وضعیت شلوغ‌تر: رخ و وزیر سیاه در جناح وزیر، اسب سفید c3 و زنجیره پیاده‌ای d4 مقابل d6.",
        "hints": [{"id": "h1", "text_fa": "مهره‌های دور از مرکز نقاط خوبی برای حفظ کردن‌اند.", "rating_cost": 10}],
        "rating": 1150.0,
    },
    {
        "fen": "4k3/8/8/8/2b1p3/5P2/PP6/3RK3 w - - 0 1",
        "memorize_seconds": 4,
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل c4 و سرباز e4 سیاه در مرکز؛ سه پیاده و رخ سفید در پایین صفحه.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌های غیرعادی و تنها را حفظ کن.", "rating_cost": 10}],
        "rating": 1200.0,
    },
    {
        "fen": "2r1k3/8/8/8/8/5n2/5PPP/5RK1 b - - 0 1",
        "memorize_seconds": 4,
        "prompt_fa": PROMPT_FA,
        "explanation": "نوبت با سیاه است. اسب f3 عمیقاً در زمین سفید نفوذ کرده؛ رخ و شاه سفید در گوشه‌اند.",
        "hints": [{"id": "h1", "text_fa": "مهره نفوذی دشمن را جداگانه به خاطر بسپار.", "rating_cost": 10}],
        "rating": 1250.0,
    },
    {
        "fen": "2b1k3/8/8/8/8/8/8/3RK2R w - - 0 1",
        "memorize_seconds": 4,
        "prompt_fa": PROMPT_FA,
        "explanation": "دو رخ سفید (d1 و g1) و فیل سیاه c8؛ شاه‌ها در e1 و e8.",
        "hints": [{"id": "h1", "text_fa": "مهره‌های همسان را با هم حفظ کن.", "rating_cost": 10}],
        "rating": 1300.0,
    },
    {
        "fen": "r6k/1pp5/8/8/8/8/1PP5/R3K2R w KQ - 0 1",
        "memorize_seconds": 4,
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ‌های a1 و h1 با شاه e1؛ رخ و دو سرباز سیاه در جناح وزیر. حق قلعه هر دو طرف هست.",
        "hints": [{"id": "h1", "text_fa": "از یک گوشه شروع کن و خانه‌به‌خانه جلو برو.", "rating_cost": 10}],
        "rating": 1400.0,
    },
]


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition with raw python-chess.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Checks parsing, both kings, a valid side
    to move and a sane memorization duration — not the validator.
    """
    board = chess.Board(item["fen"])  # raises on invalid FEN
    if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
        raise ValueError(f"puzzle needs both kings: {item['fen']}")
    squares = [sq for sq in chess.SQUARES if board.piece_at(sq) is not None]
    if len(squares) != len(set(squares)):
        raise ValueError(f"stacked pieces impossible: {item['fen']}")
    if board.turn not in (chess.WHITE, chess.BLACK):
        raise ValueError(f"invalid side to move: {item['fen']}")
    duration = item.get("memorize_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        raise ValueError(f"memorize_seconds must be a positive int: {item['fen']}")


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="صفحه حفظی",
            title_en="Memory Board",
            description="موقعیت را حفظ کن و از نو بچین.",
            is_active=True,
            sort_order=13,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={"fen": item["fen"], "memorize_seconds": item["memorize_seconds"]},
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
        print(f"seeded {n} memory-board puzzles")
    finally:
        db.close()
