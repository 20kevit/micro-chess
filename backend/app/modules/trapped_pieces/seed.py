"""Seed/demo puzzles for Trapped Pieces.

Run:  python -m app.modules.trapped_pieces.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN via trapped_squares, so they are
verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle
from app.modules.trapped_pieces.validator import SLUG, trapped_squares

# Each entry: fen, prompt, explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "اسب a1 گرفتار است؛ سربازهای خودی b3 و c2 همه پرش‌هایش را بسته‌اند.",
        "hints": [{"id": "h1", "text_fa": "اسب گوشه فقط چند پرش دارد؛ ببین همه بسته‌اند یا نه.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "2b1k3/1p1p4/8/8/8/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "فیل c8 گرفتار است؛ سربازهای خودی b7 و d7 هر دو قطرش را بسته‌اند.",
        "hints": [{"id": "h1", "text_fa": "قطرهای فیل را دنبال کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/P7/RN4K1 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "رخ a1 گرفتار است؛ سرباز a2 ستون و اسب b1 ردیف را بسته‌اند. اسب b1 خودش آزاد است.",
        "hints": [{"id": "h1", "text_fa": "رخ فقط مستقیم می‌رود؛ هر دو جهتش را ببین.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "سرباز سفید e3 و سرباز سیاه e4 همدیگر را قفل کرده‌اند؛ هیچ‌کدام جلو یا مورب حرکتی ندارند.",
        "hints": [{"id": "h1", "text_fa": "سرباز روبه‌رو همدیگر را می‌بندند.", "rating_cost": 10}],
        "rating": 900.0,
    },
    {
        "fen": "4rk2/8/8/8/8/8/4N3/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "اسب e2 آچمز است ولی گرفتار نیست؛ حرکت شبه‌قانونی دارد پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "آچمز با گرفتار فرق دارد.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/1PPPPP2/RN2K2R w K - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "همه مهره‌ها حداقل یک حرکت دارند؛ چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "اگر حتی یک حرکت هست، گرفتار نیست.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/8/6p1/5PK1/7N w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "اسب h1 سرباز g3 را می‌زند؛ پس گرفتار نیست و چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "زدن هم یک حرکت است.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/2PPP3/2BQK3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "وزیر d1 گرفتار است؛ مهره‌های خودی همه جهتش را بسته‌اند. فیل c1 با b2 آزاد است.",
        "hints": [{"id": "h1", "text_fa": "همه هشت جهت وزیر را ببین.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "2bqk3/1pppp3/8/8/8/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "فیل c8 و وزیر d8 هر دو گرفتارند؛ سربازهای خودی همه راه‌ها را بسته‌اند.",
        "hints": [{"id": "h1", "text_fa": "گاهی بیشتر از یک مهره گرفتار است.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/3p4/3P4/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "سربازهای d3 و d4 همدیگر را قفل کرده‌اند.",
        "hints": [{"id": "h1", "text_fa": "سرباز مورب خالی را هم بررسی کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k2n/5pp1/6p1/8/8/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "اسب h8 گرفتار است چون f7 و g6 پر از سرباز خودی‌اند؛ سرباز g7 هم پشت g6 قفل است.",
        "hints": [{"id": "h1", "text_fa": "پرش‌های اسب را یکی‌یکی ببین.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "2b1k3/1p1p4/8/8/8/8/P7/RN4K1 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "رخ a1 در گوشه و فیل c8 بالای صفحه هر دو گرفتارند.",
        "hints": [{"id": "h1", "text_fa": "کل صفحه را بگرد، نه فقط یک گوشه.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/6PP/6KR w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "رخ h1 گرفتار است؛ شاه g1 و سرباز h2 راهش را بسته‌اند. شاه هیچ‌وقت گرفتار نیست.",
        "hints": [{"id": "h1", "text_fa": "شاه را هیچ‌وقت انتخاب نکن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "سرباز e4 به e5 و سرباز e2 به e3 می‌روند؛ چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "یک خانه خالی جلو یعنی آزاد.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/1P1P4/2B1K3 w - - 0 1",
        "prompt_fa": "مهره‌های گرفتار را انتخاب کن.",
        "explanation": "فیل c1 گرفتار است؛ سربازهای خودی b2 و d2 هر دو قطرش را بسته‌اند.",
        "hints": [{"id": "h1", "text_fa": "فیل گوشه فقط دو قطر کوتاه دارد.", "rating_cost": 5}],
        "rating": 800.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="مهره‌های گرفتار",
            title_en="Trapped Pieces",
            description="مهره‌هایی که هیچ حرکت قانونی ندارند را پیدا کن.",
            is_active=True,
            sort_order=15,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        squares = trapped_squares(item["fen"])
        answer = {"squares": squares}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={"fen": item["fen"], "mode": "standard"},
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
        print(f"seeded {n} trapped-pieces puzzles")
    finally:
        db.close()
