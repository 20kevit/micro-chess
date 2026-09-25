"""Seed/demo puzzles for Legal Destinations.

Run:  python -m app.modules.legal_destinations.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN + target + rule profile via legal_destinations,
so they are verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.legal_destinations.validator import IGNORE_ENEMY_ATTACKS, SLUG, STANDARD, legal_destinations
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

# Each entry: fen (side to move owns the target), from, profile, prompt,
# explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/8/8/3N4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی اسب در d4 را انتخاب کن.",
        "explanation": "اسب در مرکز ۸ مقصد دارد و از روی مهره‌ها می‌پرد.",
        "hints": [{"id": "h1", "text_fa": "اسب به شکل L حرکت می‌کند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/1N2K3 w - - 0 1",
        "from": "b1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی اسب در b1 را انتخاب کن.",
        "explanation": "اسب در گوشه فقط ۳ مقصد دارد: a3 و c3 و d2.",
        "hints": [{"id": "h1", "text_fa": "گوشه صفحه جای کمی برای اسب دارد.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/3p4/2B5/8/3P4/4K3 w - - 0 1",
        "from": "c4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی فیل در c4 را انتخاب کن.",
        "explanation": "فیل سرباز d5 را می‌زند و پشت آن نمی‌تواند برود؛ سرباز خودی d2 راه را بسته است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که زده می‌شود، پشتش راه نیست.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/R3K3 w - - 0 1",
        "from": "a1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی رخ در a1 را انتخاب کن.",
        "explanation": "رخ در ستون a و ردیف اول تا شاه خودی جلو می‌رود.",
        "hints": [{"id": "h1", "text_fa": "رخ صاف حرکت می‌کند و از شاه خودی رد نمی‌شود.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/3p4/3R4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی رخ در d4 را انتخاب کن.",
        "explanation": "رخ سرباز d5 را می‌زند ولی از آن جلوتر نمی‌رود.",
        "hints": [{"id": "h1", "text_fa": "خانه‌ای که مهره دشمن در آن است، آخرین خانه آن سمت است.", "rating_cost": 10}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1",
        "from": "d4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی وزیر در d4 را انتخاب کن.",
        "explanation": "وزیر در مرکز مثل رخ و فیل با هم حرکت می‌کند: ۲۷ مقصد.",
        "hints": [{"id": "h1", "text_fa": "هم مسیرهای رخ و هم مسیرهای فیل را بشمار.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/1PP5/Q3K3 w - - 0 1",
        "from": "a1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی وزیر در a1 را انتخاب کن.",
        "explanation": "سربازهای خودی b2 و c2 راه مورب را بسته‌اند؛ فقط ستون a و ردیف اول.",
        "hints": [{"id": "h1", "text_fa": "مهره خودی را نمی‌توانی بزنی یا از آن رد شوی.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
        "from": "e2",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی سرباز در e2 را انتخاب کن.",
        "explanation": "سرباز از خانه اول می‌تواند یک یا دو خانه جلو برود: e3 و e4.",
        "hints": [{"id": "h1", "text_fa": "سرباز در حرکت اول دو خانه هم می‌تواند برود.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/3p1p2/4P3/8/8/4K3 w - - 0 1",
        "from": "e4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی سرباز در e4 را انتخاب کن.",
        "explanation": "سرباز e5 می‌رود و هر دو سرباز d5 و f5 را می‌تواند بزند.",
        "hints": [{"id": "h1", "text_fa": "سرباز مورب فقط وقتی می‌رود که مهره دشمن آنجا باشد.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/3p4/4P3/8/4K3 w - - 0 1",
        "from": "e3",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی سرباز در e3 را انتخاب کن.",
        "explanation": "سرباز e4 می‌رود و سرباز d4 را می‌زند؛ خانه f4 خالیِ مورب مقصد نیست.",
        "hints": [{"id": "h1", "text_fa": "خانه مورب خالی را انتخاب نکن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
        "from": "e1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی شاه در e1 را انتخاب کن.",
        "explanation": "شاه به هر ۵ خانه اطراف می‌تواند برود چون هیچ‌کدام زیر ضربه نیست.",
        "hints": [{"id": "h1", "text_fa": "شاه یک خانه به هر سمت می‌رود.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/4r3/8/8/8/8/8/4K3 w - - 0 1",
        "from": "e1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی شاه در e1 را انتخاب کن.",
        "explanation": "رخ سیاه ستون e را می‌زند، پس شاه نمی‌تواند به e2 برود.",
        "hints": [{"id": "h1", "text_fa": "شاه حق ندارد به خانه زیر ضربه برود.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "8/8/8/8/8/2k5/3r4/4K3 w - - 0 1",
        "from": "e1",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی شاه در e1 را انتخاب کن.",
        "explanation": "تنها f1 امن است؛ رخ d2 را شاه سیاه دفاع می‌کند و بقیه خانه‌ها زیر ضربه‌اند.",
        "hints": [
            {"id": "h1", "text_fa": "مهره‌ای که دفاع می‌شود را نمی‌توانی بزنی.", "rating_cost": 10},
            {"id": "h2", "text_fa": "فقط یک خانه امن مانده است.", "rating_cost": 15},
        ],
        "rating": 1200.0,
    },
    {
        "fen": "4k3/4r3/8/8/8/8/8/4K3 w - - 0 1",
        "from": "e1",
        "profile": IGNORE_ENEMY_ATTACKS,
        "prompt_fa": "با قانون ویژه: مقصدهای شاه در e1 را انتخاب کن (ضربه دشمن مهم نیست).",
        "explanation": "در این قانون ویژه، حمله دشمن خانه را ممنوع نمی‌کند؛ هر ۵ خانه اطراف مقصد است.",
        "hints": [{"id": "h1", "text_fa": "این بار خانه زیر ضربه هم مجاز است.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4K3/8/8/8/3n4/8/8/4k3 b - - 0 1",
        "from": "d4",
        "profile": STANDARD,
        "prompt_fa": "مقصدهای قانونی اسب سیاه در d4 را انتخاب کن.",
        "explanation": "نوبت با سیاه است؛ اسب سیاه در مرکز ۸ مقصد دارد.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت دقت کن: مهره سیاه حرکت می‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="مقصدهای قانونی",
            title_en="Legal Destinations",
            description="مقصدهای قانونی مهره مشخص‌شده را پیدا کن.",
            is_active=True,
            sort_order=1,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        squares = legal_destinations(item["fen"], item["from"], item["profile"])
        answer = {"squares": squares, "from": item["from"], "profile": item["profile"]}
        stage_validated_puzzle(
            db,
            {
                "exercise_slug": SLUG,
                "fen": item["fen"],
                "position_json": {"from": item["from"], "profile": item["profile"]},
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
        print(f"seeded {n} legal-destinations puzzles")
    finally:
        db.close()
