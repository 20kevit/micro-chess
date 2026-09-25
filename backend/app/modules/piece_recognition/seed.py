"""Seed/demo puzzles for Piece Recognition.

Run:  python -m app.modules.piece_recognition.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN + target via squares_for_target, so they
are verifiable; tests/test_piece_recognition.py recomputes them independently.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.piece_recognition.validator import SLUG, TARGETS, squares_for_target
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Each entry: fen, target key (see TARGETS), prompt, explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": STARTPOS,
        "target": "white-pawn",
        "prompt_fa": "همه سربازهای سفید را پیدا کن.",
        "explanation": "در شروع بازی، هشت سرباز سفید در ردیف دوم (a2 تا h2) هستند.",
        "hints": [{"id": "h1", "text_fa": "سربازهای سفید در ردیف ۲ ایستاده‌اند.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": STARTPOS,
        "target": "black-knight",
        "prompt_fa": "همه اسب‌های سیاه را پیدا کن.",
        "explanation": "اسب‌های سیاه در شروع بازی در b8 و g8 هستند.",
        "hints": [{"id": "h1", "text_fa": "اسب‌ها کنار رخ و فیل شروع می‌کنند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": STARTPOS,
        "target": "white-bishop",
        "prompt_fa": "همه فیل‌های سفید را پیدا کن.",
        "explanation": "فیل‌های سفید در شروع بازی در c1 و f1 هستند.",
        "hints": [{"id": "h1", "text_fa": "فیل‌ها روی خانه‌های c و f ردیف اول هستند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": STARTPOS,
        "target": "black-rook",
        "prompt_fa": "همه رخ‌های سیاه را پیدا کن.",
        "explanation": "رخ‌های سیاه در شروع بازی در a8 و h8 (گوشه‌ها) هستند.",
        "hints": [{"id": "h1", "text_fa": "رخ‌ها در گوشه‌های صفحه شروع می‌کنند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": STARTPOS,
        "target": "queen-any",
        "prompt_fa": "همه وزیرها را پیدا کن.",
        "explanation": "وزیر سفید در d1 و وزیر سیاه در d8 است.",
        "hints": [{"id": "h1", "text_fa": "وزیرها در ستون d هستند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": STARTPOS,
        "target": "minor-white",
        "prompt_fa": "همه سوارهای سبک سفید (اسب و فیل) را پیدا کن.",
        "explanation": "اسب‌های سفید b1 و g1 و فیل‌های سفید c1 و f1 هستند.",
        "hints": [
            {"id": "h1", "text_fa": "سوار سبک یعنی اسب و فیل.", "rating_cost": 5},
            {"id": "h2", "text_fa": "بین رخ و وزیر را نگاه کن.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "fen": "8/8/8/8/3p4/8/PP6/8 w - - 0 1",
        "target": "black-pawn",
        "prompt_fa": "سرباز سیاه کجاست؟",
        "explanation": "تنها سرباز سیاه در d4 است.",
        "hints": [{"id": "h1", "text_fa": "وسط صفحه را نگاه کن.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "6k1/pp4pp/8/8/8/8/PP4PP/6K1 w - - 0 1",
        "target": "white-pawn",
        "prompt_fa": "همه سربازهای سفید را پیدا کن.",
        "explanation": "سربازهای سفید در a2 و b2 و g2 و h2 هستند.",
        "hints": [{"id": "h1", "text_fa": "ردیف دوم را بررسی کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "8/8/5n2/8/8/2N5/8/4K2k w - - 0 1",
        "target": "white-knight",
        "prompt_fa": "همه اسب‌های سفید را پیدا کن.",
        "explanation": "اسب‌های سفید در f6 و c3 هستند.",
        "hints": [{"id": "h1", "text_fa": "یکی بالا و یکی وسط صفحه است.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "8/8/8/1b6/8/4B3/8/4K2k w - - 0 1",
        "target": "black-bishop",
        "prompt_fa": "فیل سیاه کجاست؟",
        "explanation": "فیل سیاه در b5 است؛ فیل e3 سفید است و جزء جواب نیست.",
        "hints": [{"id": "h1", "text_fa": "به رنگ مهره دقت کن، نه فقط شکل آن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "r6k/8/8/8/8/8/8/R5K1 w - - 0 1",
        "target": "black-rook",
        "prompt_fa": "رخ سیاه کجاست؟",
        "explanation": "رخ سیاه در a8 است؛ رخ a1 سفید است.",
        "hints": [{"id": "h1", "text_fa": "گوشه‌های صفحه را نگاه کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "target": "queen-any",
        "prompt_fa": "همه وزیرها را پیدا کن.",
        "explanation": "وزیر سیاه در d8 و وزیر سفید در d1 است.",
        "hints": [{"id": "h1", "text_fa": "ستون d را بررسی کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "8/1b6/8/2n5/8/5B2/8/4K2k w - - 0 1",
        "target": "minor-black",
        "prompt_fa": "همه سوارهای سبک سیاه (اسب و فیل) را پیدا کن.",
        "explanation": "فیل سیاه در b7 و اسب سیاه در c5 است؛ فیل f3 سفید است.",
        "hints": [
            {"id": "h1", "text_fa": "سوار سبک یعنی اسب و فیل.", "rating_cost": 5},
            {"id": "h2", "text_fa": "نیمه بالای صفحه را نگاه کن.", "rating_cost": 10},
        ],
        "rating": 1100.0,
    },
    {
        "fen": "8/8/8/8/8/5N2/5B2/4K2k w - - 0 1",
        "target": "minor-white",
        "prompt_fa": "همه سوارهای سبک سفید (اسب و فیل) را پیدا کن.",
        "explanation": "اسب سفید در f3 و فیل سفید در f2 است.",
        "hints": [{"id": "h1", "text_fa": "ستون f را بررسی کن.", "rating_cost": 5}],
        "rating": 1050.0,
    },
    {
        "fen": "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        "target": "white-pawn",
        "prompt_fa": "همه سربازهای سفید را پیدا کن.",
        "explanation": "سربازها در a2 و b2 و c2 و d2 و e4 و f2 و g2 و h2 هستند؛ سرباز e جلو رفته است.",
        "hints": [
            {"id": "h1", "text_fa": "یک سرباز از ردیف دوم جلو رفته است.", "rating_cost": 10},
            {"id": "h2", "text_fa": "خانه e4 را بررسی کن.", "rating_cost": 15},
        ],
        "rating": 1200.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="تشخیص مهره",
            title_en="Piece Recognition",
            description="خانه‌های مهره‌های خواسته‌شده را روی صفحه پیدا کن.",
            is_active=True,
            sort_order=0,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        target = TARGETS[item["target"]]
        answer = {"squares": squares_for_target(item["fen"], target), "target": item["target"]}
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": item["fen"],
                "position_json": {"target": item["target"]},
                "answer_json": answer,
                "hint_json": {"hints": item["hints"]},
                "prompt_fa": item["prompt_fa"],
                "explanation": item["explanation"],
                "initial_rating": item["rating"],
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
        print(f"seeded {n} piece-recognition puzzles")
    finally:
        db.close()
