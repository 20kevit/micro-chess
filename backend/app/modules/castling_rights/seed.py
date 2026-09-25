"""Seed/demo puzzles for Castling Rights.

Run:  python -m app.modules.castling_rights.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN via legal_castling_options, so they are
verifiable; tests independently recompute the four castling moves with
python-chess legal move generation.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.castling_rights.validator import SLUG, legal_castling_options
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

PROMPT_FA = "مشخص کن کدام قلعه‌ها در این وضعیت قانونی هستند."

# Each entry: fen, explanation (teaches WHY each option is or is not legal),
# hints, rating. Answers are derived from the FEN at seed time.
PUZZLES: list[dict] = [
    {
        "fen": "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "هر چهار قلعه قانونی است؛ حق قلعه وجود دارد، مسیرها خالی‌اند و هیچ خانه‌ای که شاه از آن می‌گذرد زیر ضربه نیست.",
        "hints": [{"id": "h1", "text_fa": "حق قلعه، مسیر خالی و امنیت شاه را هر سه بررسی کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "r3kb1r/8/8/8/8/8/8/R3K2R w Kk - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فقط قلعه کوتاه سفید قانونی است؛ فیل f8 مسیر قلعه کوتاه سیاه را بسته و حق قلعه‌های دیگر اصلاً وجود ندارد.",
        "hints": [{"id": "h1", "text_fa": "اول ببین حق قلعه در FEN هست یا نه.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "rn2k2r/8/8/8/8/8/8/R3K2R w Qq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فقط قلعه بزرگ سفید قانونی است؛ اسب b8 مسیر قلعه بزرگ سیاه را بسته و حق‌های دیگر وجود ندارند.",
        "hints": [{"id": "h1", "text_fa": "قلعه بزرگ به خانه خالی b هم نیاز دارد.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "r1b1k2r/8/8/8/8/8/8/R3K2R b kq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فقط قلعه کوتاه سیاه قانونی است؛ فیل c8 مسیر قلعه بزرگ را بسته و سفید هیچ حقی ندارد.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت هم توجه کن، ولی حق هر طرف جداگانه بررسی می‌شود.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/R3K1NR b Kq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فقط قلعه بزرگ سیاه قانونی است؛ اسب g1 مسیر قلعه کوتاه سفید را بسته و حق قلعه کوتاه سیاه وجود ندارد.",
        "hints": [{"id": "h1", "text_fa": "یک مهره در مسیر، کل قلعه را باطل می‌کند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "با وجود حق قلعه، همه مسیرها بسته‌اند؛ پس هیچ قلعه‌ای قانونی نیست.",
        "hints": [{"id": "h1", "text_fa": "حق قلعه به‌تنهایی کافی نیست؛ مسیر هم باید خالی باشد.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "صفحه آماده قلعه به نظر می‌رسد، ولی حق قلعه در FEN وجود ندارد؛ پس هیچ قلعه‌ای قانونی نیست.",
        "hints": [{"id": "h1", "text_fa": "بدون حق قلعه، ظاهر صفحه مهم نیست.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/R3KN1R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب f1 مسیر قلعه کوتاه سفید را بسته، ولی قلعه بزرگ سفید و هر دو قلعه سیاه قانونی‌اند.",
        "hints": [{"id": "h1", "text_fa": "مسیر هر قلعه را جداگانه بررسی کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "r3k2r/8/8/8/1b6/8/8/R3K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل b4 شاه سفید را کیش داده، پس هر دو قلعه سفید باطل‌اند؛ قلعه‌های سیاه سالم‌اند.",
        "hints": [{"id": "h1", "text_fa": "شاهِ زیر کیش حق قلعه رفتن ندارد.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "r3k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل c4 خانه f1 را می‌زند؛ شاهی که از خانه زیر ضربه عبور کند نمی‌تواند قلعه کوتاه برود. قلعه بزرگ سفید و هر دو قلعه سیاه قانونی‌اند.",
        "hints": [{"id": "h1", "text_fa": "خانه‌های میانی مسیر هم باید امن باشند.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/7n/8/R3K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب h3 خانه g1 را می‌زند؛ مقصد شاه باید امن باشد، پس قلعه کوتاه سفید باطل است. بقیه قلعه‌ها قانونی‌اند.",
        "hints": [{"id": "h1", "text_fa": "مقصد نهایی شاه هم باید امن باشد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب b1 مسیر رخ را بسته، پس قلعه بزرگ سفید ممکن نیست؛ هرچند شاه از b1 عبور نمی‌کند. بقیه قلعه‌ها قانونی‌اند.",
        "hints": [{"id": "h1", "text_fa": "در قلعه بزرگ، خانه b هم باید خالی باشد.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/R3K3 w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "پرچم قلعه کوتاه سفید هست ولی رخ h1 وجود ندارد؛ پرچم کهنه به‌تنهایی کافی نیست. قلعه بزرگ سفید و هر دو قلعه سیاه قانونی‌اند.",
        "hints": [{"id": "h1", "text_fa": "بودن شاه و رخ در خانه‌شان را هم بررسی کن.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "r3k2r/8/8/8/8/8/8/R6R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "شاه سفید اصلاً در صفحه نیست، پس هر دو قلعه سفید باطل‌اند؛ قلعه‌های سیاه سالم‌اند.",
        "hints": [{"id": "h1", "text_fa": "بدون شاه، قلعه‌ای در کار نیست.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "rn2k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "هر چهار حق وجود دارد ولی فقط دو قلعه قانونی است: فیل c4 خانه f1 را می‌زند (کوتاه سفید باطل) و اسب b8 مسیر قلعه بزرگ سیاه را بسته است.",
        "hints": [{"id": "h1", "text_fa": "هر چهار گزینه را مستقل از هم بررسی کن.", "rating_cost": 10}],
        "rating": 1100.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="حقوق قلعه‌رفتن",
            title_en="Castling Rights",
            description="مشخص کن کدام قلعه‌ها در وضعیت فعلی قانونی هستند.",
            is_active=True,
            sort_order=20,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        options = legal_castling_options(item["fen"])
        answer = {"options": options}
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": item["fen"],
                "position_json": {"fen": item["fen"], "mode": "standard"},
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
        print(f"seeded {n} castling-rights puzzles")
    finally:
        db.close()
