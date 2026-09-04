"""Seed/demo puzzles for Give Check.

Run:  python -m app.modules.give_check.seed
Idempotent: skips when puzzles for the slug already exist.
Each entry carries an example checking move that is independently verified
with raw python-chess (legal + gives check) before insert; invalid entries
fail loudly instead of seeding a broken puzzle. Validation itself never
depends on the example: any legal checking move is accepted.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.give_check.validator import MODES, SLUG
from app.modules.puzzles.models import Puzzle

PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}

# Each entry: fen, mode, example from/to (+promotion), prompt, explanation,
# hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/8/8/8/8/8/R3K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "a1", "to": "a8"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "رخ از a1 به a8 می‌رود و در ستون a به شاه سیاه کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "ستون رخ تا شاه حریف باز است.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/2B5/8/8/4K3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "c4", "to": "b5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "فیل از c4 به b5 می‌رود و از قطر به شاه e8 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "قطر فیل تا شاه حریف را دنبال کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "d1", "to": "h5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "وزیر از d1 به h5 می‌رود و از قطر به شاه e8 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم مثل فیل مورب می‌رود.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/1N6/8/8/8/4K3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "b5", "to": "d6"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "اسب از b5 به d6 می‌پرد و به شاه e8 کیش می‌دهد؛ اسب از روی مهره‌ها می‌پرد.",
        "hints": [{"id": "h1", "text_fa": "اسب به شکل L حرکت می‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "8/8/5k2/8/4P3/8/8/4K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "e4", "to": "e5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "سرباز از e4 به e5 می‌رود و به شاه f6 کیش می‌دهد؛ سرباز هم می‌تواند کیش بدهد.",
        "hints": [{"id": "h1", "text_fa": "سرباز به خانه‌ای می‌رود که شاه را بزند.", "rating_cost": 10}],
        "rating": 900.0,
    },
    {
        "fen": "k7/8/8/8/8/8/K6K/R7 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "a2", "to": "b3"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "شاه از a2 کنار می‌رود و رخ a1 به شاه a8 کیش کشف‌شده می‌دهد؛ خود شاه هم می‌تواند کیش بدهد.",
        "hints": [{"id": "h1", "text_fa": "گاهی کنار رفتن شاه، کیش کشف‌شده می‌سازد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "7k/8/8/8/3N4/8/1B6/4K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "d4", "to": "f5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "اسب از d4 کنار می‌رود و فیل b2 به شاه h8 کیش کشف‌شده می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "کدام مهره جلوی حمله را گرفته است؟", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "8/8/4k3/3p4/3Q4/8/8/4K3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "d4", "to": "d5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "وزیر سرباز d5 را می‌زند و از همان خانه به شاه e6 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره هم می‌تواند کیش بدهد.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "d4", "to": "d8"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "وزیر وسط صفحه چند کیش مختلف دارد؛ مثلاً d8 یا h8. هر کیش قانونی قبول است.",
        "hints": [{"id": "h1", "text_fa": "وزیر وسط صفحه را خوب نگاه کن؛ بیش از یک کیش هست.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/3p4/8/8/8/8/8/3QK3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "d1", "to": "h5"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "حرکت d1 به d8 غیرقانونی است چون سرباز d7 راه را بسته؛ ولی d1 به h5 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "حرکت مسدودشده کیش نیست؛ راه دیگری پیدا کن.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "e2", "to": "e7"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "وزیر به ستون e میخکوب شده و فقط در همان ستون می‌تواند حرکت کند؛ e7 به شاه d8 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "مهره میخکوب‌شده فقط در خط میخکوبی حرکت می‌کند.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "k7/8/8/8/8/8/8/R3K3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "a1", "to": "a7"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "رخ از گوشه به a7 می‌رود و به شاه گوشه a8 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "شاه گوشه از ستون خودش ضربه می‌خورد.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "d4", "to": "d1"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "سفید خودش کیش است؛ وزیر با d1 هم جلوی کیش را می‌گیرد و هم به شاه d8 کیش می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "اول از کیش خارج شو، بعد کیش بده.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4k3/8/8/5N2/8/8/8/4K3 w - - 0 1",
        "mode": "appropriate-checks",
        "example": {"from": "f5", "to": "d6"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "اسب f5 دو کیش دارد: d6 و g7. هر کدام را بازی کنی قبول است.",
        "hints": [{"id": "h1", "text_fa": "مقصدهای اسب را یکی‌یکی امتحان کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "7k/6P1/8/8/8/8/8/4K3 w - - 0 1",
        "mode": "all-checks",
        "example": {"from": "g7", "to": "g8", "promotion": "q"},
        "prompt_fa": "حرکتی پیدا کن که شاه حریف را کیش کند.",
        "explanation": "سرباز به g8 وزیر می‌شود و به شاه h8 کیش می‌دهد؛ موقع ترفیع، مهره را هم بگو.",
        "hints": [{"id": "h1", "text_fa": "ترفیع سرباز هم می‌تواند کیش بدهد.", "rating_cost": 10}],
        "rating": 950.0,
    },
]


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition with raw python-chess.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses direct move generation, not the validator.
    """
    if item["mode"] not in MODES:
        raise ValueError(f"unknown mode: {item['mode']}")
    board = chess.Board(item["fen"])  # raises on invalid FEN
    example = item["example"]
    move = chess.Move(
        chess.parse_square(example["from"]),
        chess.parse_square(example["to"]),
        promotion=PROMOTIONS.get(example.get("promotion")) if example.get("promotion") else None,
    )
    if move not in board.legal_moves:
        raise ValueError(f"example move not legal: {item['fen']} {example}")
    board.push(move)
    try:
        if not board.is_check():
            raise ValueError(f"example move gives no check: {item['fen']} {example}")
    finally:
        board.pop()


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="کیش دادن",
            title_en="Give Check",
            description="حرکتی پیدا کن که شاه حریف را کیش کند.",
            is_active=True,
            sort_order=6,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"], "mode": item["mode"], "example": item["example"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=item["fen"],
            position_json={"fen": item["fen"], "mode": item["mode"]},
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
        print(f"seeded {n} give-check puzzles")
    finally:
        db.close()
