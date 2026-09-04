"""Seed/demo puzzles for Hanging Pieces.

Run:  python -m app.modules.hanging_pieces.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN via hanging_squares, so they are
verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.hanging_pieces.validator import SLUG, hanging_squares
from app.modules.puzzles.models import Puzzle

# Each entry: fen, prompt, explanation (teaches the concept, not just the
# answer), hints, rating. Answers are derived from the FEN at seed time.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/2b5/8/4N3/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "اسب سفید در e4 توسط فیل سیاه مورد حمله است، اما هیچ مهره سفید دیگری از آن دفاع نمی‌کند؛ بنابراین آویزان است.",
        "hints": [{"id": "h1", "text_fa": "ببین کدام مهره دشمن به آن حمله می‌کند و چه کسی از آن دفاع می‌کند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/5n2/2b5/3PP3/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز d4 زیر ضربه فیل است، سرباز e4 زیر ضربه اسب است، و فیل c5 زیر ضربه سرباز d4 است؛ هیچ‌کدام مدافعی ندارند.",
        "hints": [{"id": "h1", "text_fa": "گاهی مهره سیاه هم آویزان است.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/5N2/5P2/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "هیچ مهره‌ای زیر ضربه دشمن نیست؛ پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "اگر مهره‌ای حمله نمی‌شود، جواب خالی است.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز e4 زیر ضربه اسب است، ولی سرباز d3 از آن دفاع می‌کند؛ پس آویزان نیست و جواب خالی است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که مدافع دارد آویزان نیست، حتی اگر حمله شود.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/2n1n3/8/3P4/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز d4 هم‌زمان توسط دو اسب حمله می‌شود و هیچ مدافعی ندارد؛ تعداد مهاجم‌ها مهم نیست، نبود مدافع مهم است.",
        "hints": [{"id": "h1", "text_fa": "مهاجم‌ها را بشمار، بعد مدافع‌ها را.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/2b1p3/3N4/2P1P3/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "اسب d4 هم فیل و هم سرباز به آن حمله می‌کنند، ولی دو سرباز c3 و e3 از آن دفاع می‌کنند؛ دفاع چندگانه هم دفاع است.",
        "hints": [{"id": "h1", "text_fa": "دفاع چند مهره هم یعنی آویزان نیست.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/4p3/5P2/6P1/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز f5 زیر ضربه است ولی سرباز g4 از آن دفاع می‌کند؛ در عوض سرباز سیاه e6 را سرباز f5 می‌زند و بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "حمله سرباز فقط مورب است، نه مستقیم.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/4pb2/5P2/3N4/2P5/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "اسب d4 زیر ضربه فیل است ولی سرباز c3 دفاعش می‌کند؛ سرباز e6 را دو مهره سفید می‌زنند و مدافعی ندارد.",
        "hints": [{"id": "h1", "text_fa": "اسب هم می‌تواند مدافع خوبی باشد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "3rk3/8/8/8/8/8/5K2/3R4 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "رخ سفید در d1 تمام ستون را زیر ضربه رخ سیاه است و مدافعی ندارد؛ رخ سیاه را شاه خودش دفاع می‌کند.",
        "hints": [{"id": "h1", "text_fa": "حمله رخ از تمام طول ستون می‌گذرد.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/2b5/3N4/8/3p4/3Q1K2 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز سیاه d2 جلوی دفاع وزیر از اسب را گرفته است؛ هم اسب d4 و هم سرباز d2 بی‌دفاع زیر ضربه‌اند.",
        "hints": [{"id": "h1", "text_fa": "مانع می‌تواند راه دفاع را هم ببندد.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4k3/8/8/8/8/3k4/2P5/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "شاه هم مهاجم و مدافع حساب می‌شود: سرباز c2 زیر ضربه شاه سیاه و بی‌دفاع است، و شاه سیاه خودش زیر ضربه سرباز c2 و بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "شاه هم می‌تواند حمله و دفاع کند.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/1b6/2P5/3K4 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "سرباز c2 زیر ضربه فیل است ولی شاه سفید d1 از آن دفاع می‌کند؛ در عوض خود فیل b3 زیر ضربه سرباز و بی‌دفاع است.",
        "hints": [{"id": "h1", "text_fa": "دفاع شاه هم دفاع است.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "r3k3/8/8/8/8/8/8/R3K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "دو رخ در گوشه روبه‌روی هم‌اند و هر دو بی‌دفاع زیر ضربه‌اند.",
        "hints": [{"id": "h1", "text_fa": "گوشه‌ها را هم بررسی کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/2b1p3/3QP3/8/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "از سه مهره دشمن، هر سه‌تایشان بی‌دفاع زیر ضربه‌اند: وزیر d4، فیل c5 و سرباز e5. سرباز خودی e4 امن است.",
        "hints": [{"id": "h1", "text_fa": "مهره به مهره جلو برو و مدافع هر کدام را پیدا کن.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4k3/8/6n1/7P/5B2/6P1/8/4K3 w - - 0 1",
        "prompt_fa": "مهره‌های آویزان را انتخاب کن.",
        "explanation": "فیل f4 زیر ضربه اسب است ولی سرباز g3 از آن دفاع می‌کند و گول‌زنک است؛ فقط اسب g6 که سرباز h5 می‌زندش آویزان است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که حمله می‌شود ولی مدافع دارد، تله است.", "rating_cost": 10}],
        "rating": 1200.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="مهره‌های آویزان",
            title_en="Hanging Pieces",
            description="مهره‌هایی که دشمن می‌زند و کسی از آن‌ها دفاع نمی‌کند را پیدا کن.",
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
        squares = hanging_squares(item["fen"])
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
        print(f"seeded {n} hanging-pieces puzzles")
    finally:
        db.close()
