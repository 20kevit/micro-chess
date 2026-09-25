"""Seed/demo puzzles for Captures.

Run:  python -m app.modules.captures.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN + hunter via capturable_squares, so they
are verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.captures.validator import SLUG, capturable_squares
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

# Each entry: fen (side to move owns the hunter), hunter square, prompt,
# explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/2p1p3/1P6/3N4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که اسب در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "اسب سربازهای c6 و e6 را می‌زند؛ سرباز خودی b5 قابل زدن نیست.",
        "hints": [{"id": "h1", "text_fa": "اسب می‌پرد؛ مهره خودی را نمی‌شود زد.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k2n/8/8/3p4/2B5/8/8/4K3 w - - 0 1",
        "from": "c4",
        "prompt_fa": "مهره‌هایی که فیل در c4 می‌تواند بزند را انتخاب کن.",
        "explanation": "فیل فقط سرباز d5 را می‌زند؛ اسب h8 دور از دسترس اوست.",
        "hints": [{"id": "h1", "text_fa": "فیل فقط روی قطر خودش مهره می‌زند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "2r1k3/8/8/3p4/3R2p1/8/8/4K3 w - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که رخ در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "رخ سرباز d5 و سرباز g4 را می‌زند؛ خانه‌های خالی که فقط می‌شود به آن‌ها رفت جواب نیست.",
        "hints": [{"id": "h1", "text_fa": "فقط خانه‌هایی که مهره دشمن در آن‌هاست.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/3pp3/3Q4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که وزیر در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "وزیر سرباز d5 را مستقیم و سرباز e5 را مورب می‌زند.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم مثل رخ و هم مثل فیل می‌زند.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/3p1p2/4P3/8/8/4K3 w - - 0 1",
        "from": "e4",
        "prompt_fa": "مهره‌هایی که سرباز در e4 می‌تواند بزند را انتخاب کن.",
        "explanation": "سرباز فقط مورب می‌زند: d5 و f5. رفتن به e5 زدن نیست.",
        "hints": [{"id": "h1", "text_fa": "سرباز جلو نمی‌زند، فقط مورب.", "rating_cost": 10}],
        "rating": 850.0,
    },
    {
        "fen": "r3k3/8/3p4/8/4P3/8/8/4K3 w - - 0 1",
        "from": "e4",
        "prompt_fa": "مهره‌هایی که سرباز در e4 می‌تواند بزند را انتخاب کن.",
        "explanation": "هیچ مهره دشمنی در قطر سرباز نیست؛ پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "اگر زدنی نیست، خالی بفرست.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/4p3/1p1P4/2B5/8/8/4K3 w - - 0 1",
        "from": "c4",
        "prompt_fa": "مهره‌هایی که فیل در c4 می‌تواند بزند را انتخاب کن.",
        "explanation": "سرباز خودی d5 راه را بسته و سرباز e6 پشت آن در امان است؛ فقط b5 زده می‌شود.",
        "hints": [{"id": "h1", "text_fa": "از روی مهره خودی نمی‌شود زد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/3p4/3p4/3R4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که رخ در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "رخ فقط سرباز d5 را می‌زند؛ سرباز d6 پشت آن پنهان است.",
        "hints": [{"id": "h1", "text_fa": "پشت اولین مهره هر جهت چیزی زده نمی‌شود.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/2p5/3p4/3R4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که رخ در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "رخ سرباز d5 را می‌زند؛ اینکه سرباز c6 از آن دفاع می‌کند هیچ فرقی نمی‌کند.",
        "hints": [{"id": "h1", "text_fa": "دفاع شدن مهره دشمن جلوی زدن را نمی‌گیرد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k1n1/6P1/8/8/8/8/8/4K3 w - - 0 1",
        "from": "g7",
        "prompt_fa": "مهره‌هایی که سرباز در g7 می‌تواند بزند را انتخاب کن.",
        "explanation": "سرباز با زدن اسب h8 وزیر می‌شود؛ رفتن به g8 زدن نیست.",
        "hints": [{"id": "h1", "text_fa": "سرباز مورب می‌زند، حتی به خانه آخر صفحه.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/p7/8/8/7p/R3K3 w - - 0 1",
        "from": "a1",
        "prompt_fa": "مهره‌هایی که رخ در a1 می‌تواند بزند را انتخاب کن.",
        "explanation": "رخ در گوشه فقط سرباز a5 را می‌زند؛ سرباز h2 به او ربطی ندارد.",
        "hints": [{"id": "h1", "text_fa": "رخ فقط در یک ستون یا ردیف با دشمن کار دارد.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/5p2/8/5pp1/3K1Q2 w - - 0 1",
        "from": "f1",
        "prompt_fa": "مهره‌هایی که وزیر در f1 می‌تواند بزند را انتخاب کن.",
        "explanation": "وزیر f2 و g2 را می‌زند؛ ولی سرباز f4 پشت f2 پنهان است.",
        "hints": [{"id": "h1", "text_fa": "مهره پشت مهره‌ای که زده می‌شود در امان است.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/p3p3/8/2B1K3 w - - 0 1",
        "from": "c1",
        "prompt_fa": "مهره‌هایی که فیل در c1 می‌تواند بزند را انتخاب کن.",
        "explanation": "فیل از گوشه دو قطر را می‌زند: a3 و e3.",
        "hints": [{"id": "h1", "text_fa": "هر دو قطر فیل را بررسی کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/8/8/1p6/2P5/N3K3 w - - 0 1",
        "from": "a1",
        "prompt_fa": "مهره‌هایی که اسب در a1 می‌تواند بزند را انتخاب کن.",
        "explanation": "اسب گوشه فقط b3 را می‌زند؛ سرباز خودی c2 قابل زدن نیست.",
        "hints": [{"id": "h1", "text_fa": "اسب گوشه فقط دو مقصد دارد.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/2P1P3/8/3n4/8/8/4K3 b - - 0 1",
        "from": "d4",
        "prompt_fa": "مهره‌هایی که اسب سیاه در d4 می‌تواند بزند را انتخاب کن.",
        "explanation": "نوبت با سیاه است؛ اسب سیاه سربازهای c6 و e6 را می‌زند.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت دقت کن: مهره سیاه شکارچی است.", "rating_cost": 5}],
        "rating": 850.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="گرفتن مهره‌ها",
            title_en="Captures",
            description="مهره‌های دشمن که شکارچی می‌تواند بزند را پیدا کن.",
            is_active=True,
            sort_order=2,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        squares = capturable_squares(item["fen"], item["from"])
        answer = {"squares": squares, "from": item["from"]}
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": item["fen"],
                "position_json": {"from": item["from"]},
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
        print(f"seeded {n} captures puzzles")
    finally:
        db.close()
