"""Seed/demo puzzles for Undefended Pieces.

Run:  python -m app.modules.undefended_pieces.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN via undefended_squares, so they are
verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle
from app.modules.undefended_pieces.validator import SLUG, undefended_squares

# Each entry: fen, prompt, explanation, hints, rating. Answers are derived
# from the FEN at seed time. Every pin-sensitive FEN below was verified with
# board.is_pinned so the absolute-pin rule (King only) is baked in.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/2b5/8/4R3/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "رخ سفید در e4 زیر ضربه فیل سیاه است و هیچ مهره سفیدی از آن دفاع نمی‌کند؛ پس بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "ببین کدام مهره دشمن به آن حمله می‌کند و چه کسی از آن دفاع می‌کند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/5n2/8/8/2B5/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "اسب سیاه در f6 زیر ضربه فیل سفید است و هیچ مهره سیاهی از آن دفاع نمی‌کند؛ پس بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌های سیاه هم می‌توانند بی‌دفاع باشند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/2b5/8/4R3/8/4Q3/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "رخ سفید در e4 زیر ضربه فیل است، ولی وزیر سفید در e2 از آن دفاع می‌کند؛ پس چیزی بی‌دفاع نیست.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که مدافع دارد بی‌دفاع نیست، حتی اگر حمله شود.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "8/8/5n2/1k2P3/r7/8/8/R3K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "رخ سفید در a1 زیر ضربه رخ سیاه است و اسب سیاه در f6 زیر ضربه سرباز سفید؛ هیچ‌کدام مدافعی ندارند.",
        "hints": [{"id": "h1", "text_fa": "سفید و سیاه را جداگانه بررسی کن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/5N2/5P2/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "هیچ مهره‌ای زیر ضربه دشمن نیست؛ پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "اگر مهره‌ای حمله نمی‌شود، جواب خالی است.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        # Example C: the white knight defends e4 geometrically but is
        # absolutely pinned to its own King, so it does NOT count.
        "fen": "4k1r1/8/1b6/8/8/4R3/6N1/6K1 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "اسب سفید در g2 روی ستون رخ سیاه میخکوب شده و نمی‌تواند مدافع باشد؛ رخ سفید در e3 بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که برای دفاع از شاه تکان نمی‌تواند بخورد، مدافع نیست.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        # Example D: the black bishop apparently attacks e6 but is
        # absolutely pinned to its own King, so it does NOT count.
        "fen": "4k3/3b4/2B1R3/8/8/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "فیل سیاه در d7 به شاه خودش میخکوب شده و مهاجم حساب نمی‌شود؛ پس چیزی بی‌دفاع نیست.",
        "hints": [{"id": "h1", "text_fa": "مهاجمی که به شاه خودش میخکوب شده، حمله نمی‌کند.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        # Example E: the black bishop shields its QUEEN (not its King), so
        # it is NOT absolutely pinned and still counts as an attacker.
        "fen": "4q2k/3b4/2B1R3/8/8/8/8/K7 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "فیل سیاه فقط جلوی وزیر است، نه شاه؛ پس همچنان مهاجم است و رخ سفید در e6 بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "میخکوبی به وزیر، میخکوبی مطلق نیست.", "rating_cost": 10}],
        "rating": 1150.0,
    },
    {
        # Example F: the black King is attacked and undefended but Kings are
        # never answers.
        "fen": "8/8/8/4k3/8/8/4Q3/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "شاه سیاه زیر ضربه است ولی شاه هرگز جواب نیست؛ پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "شاه را هرگز انتخاب نکن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "دو سرباز مورب همدیگر را می‌زنند و هیچ‌کدام مدافعی ندارند.",
        "hints": [{"id": "h1", "text_fa": "حمله سرباز فقط مورب است.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/4p3/4P3/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "سربازی که مستقیم جلوی سرباز دیگر است به آن حمله نمی‌کند؛ پس چیزی بی‌دفاع نیست.",
        "hints": [{"id": "h1", "text_fa": "سرباز از روبه‌رو حمله نمی‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/5n2/3N4/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "دو اسب با پرش همدیگر را می‌زنند و هیچ‌کدام مدافعی ندارند.",
        "hints": [{"id": "h1", "text_fa": "اسب از روی مهره‌ها می‌پرد.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "3rk3/8/8/3p4/3R4/8/8/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "سرباز سیاه راه رخ سیاه را بسته و خودش هم توسط همان رخ دفاع می‌شود؛ پس چیزی بی‌دفاع نیست.",
        "hints": [{"id": "h1", "text_fa": "مانع، هم حمله و هم دفاع را می‌بندد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/2b2n2/4P3/4P3/4K3/8/8 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "سرباز e4 زیر ضربه فیل است ولی شاه سفید از آن دفاع می‌کند؛ فقط اسب سیاه در f6 بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "دفاع شاه هم دفاع است.", "rating_cost": 5}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/3k4/2P5/4K3 w - - 0 1",
        "prompt_fa": "کدام مهره‌ها بی‌دفاع هستند؟",
        "explanation": "شاه سیاه به سرباز حمله می‌کند و خود شاه هم زیر ضربه سرباز است، ولی شاه جواب نیست؛ فقط سرباز c2 بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "شاه حمله و دفاع می‌کند، ولی هرگز انتخاب نمی‌شود.", "rating_cost": 10}],
        "rating": 1050.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="مهره‌های بی‌دفاع",
            title_en="Undefended Pieces",
            description="مهره‌هایی که دشمن می‌زند و هیچ‌کس از آن‌ها دفاع نمی‌کند را پیدا کن.",
            is_active=True,
            sort_order=3,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        squares = undefended_squares(item["fen"])
        answer = {"squares": squares}
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
        print(f"seeded {n} undefended-pieces puzzles")
    finally:
        db.close()
