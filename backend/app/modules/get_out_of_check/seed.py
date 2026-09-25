"""Seed/demo puzzles for Get Out of Check.

Run:  python -m app.modules.get_out_of_check.seed
Idempotent: skips when puzzles for the slug already exist.
Each entry carries an example escaping move that is independently verified
with raw python-chess (starts in check, move legal, king safe afterwards)
before insert; invalid entries fail loudly instead of seeding a broken
puzzle. Validation itself never depends on the example: any legal escape
is accepted.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.get_out_of_check.validator import SLUG
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}

# Each entry: fen (side to move starts in check), example from/to
# (+promotion), prompt, explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "d1"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "رخ e2 از عرض به شاه کیش می‌دهد؛ شاه به d1 می‌رود و از کیش خارج می‌شود.",
        "hints": [{"id": "h1", "text_fa": "شاه به خانه‌ای می‌رود که زیر ضربه نباشد.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/1b6/8/2N5/4K3 w - - 0 1",
        "example": {"from": "c2", "to": "b4"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "اسب c2 فیل b4 را که کیش می‌دهد می‌زند و شاه نجات پیدا می‌کند.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره کیش‌دهنده هم راه نجات است.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4r3/8/8/8/8/3B4/8/4K3 w - - 0 1",
        "example": {"from": "d3", "to": "e2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "رخ e8 از ستون کیش می‌دهد؛ فیل با e2 جلوی آن را می‌گیرد.",
        "hints": [{"id": "h1", "text_fa": "جلوی کیش خطی می‌شود مهره گذاشت.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/5n2/6P1/4K3 w - - 0 1",
        "example": {"from": "g2", "to": "f3"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "اسب f3 به شاه کیش می‌دهد؛ سرباز g2 آن را می‌زند.",
        "hints": [{"id": "h1", "text_fa": "اسب را می‌شود زد؛ جلوی آن نمی‌شود مهره گذاشت.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/3p4/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "d2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "سرباز d2 به شاه کیش می‌دهد؛ شاه آن را می‌زند چون مدافعی ندارد.",
        "hints": [{"id": "h1", "text_fa": "شاه خودش هم می‌تواند مهره کیش‌دهنده را بزند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/1b6/5n2/8/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "d1"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "کیش دوبل است: هم فیل و هم اسب کیش می‌دهند. در کیش دوبل فقط حرکت شاه نجات می‌دهد.",
        "hints": [{"id": "h1", "text_fa": "دو مهاجم را با یک حرکت نمی‌شود گرفت؛ شاه باید حرکت کند.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "3k4/8/8/8/8/8/8/3rK3 w - - 0 1",
        "example": {"from": "e1", "to": "e2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "رخ d1 از خانه مجاور کیش می‌دهد و جلوی آن نمی‌شود مهره گذاشت؛ شاه به e2 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "کیش از خانه مجاور را نمی‌شود مسدود کرد.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "e2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "وزیر e2 از خانه مجاور کیش می‌دهد و مدافعی ندارد؛ شاه آن را می‌زند و این تنها راه نجات است.",
        "hints": [{"id": "h1", "text_fa": "گاهی تنها راه، زدن مهره مهاجم با شاه است.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/1q6/8/2P5/r1B1K3 w - - 0 1",
        "example": {"from": "c2", "to": "c3"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "سرباز c2 به c3 می‌رود و جلوی کیش وزیر را می‌گیرد. دقت کن فیل c1 میخکوب است و نمی‌تواند به d2 برود.",
        "hints": [{"id": "h1", "text_fa": "مهره میخکوب‌شده نمی‌تواند جلوی کیش را بگیرد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/1b6/8/4r3/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "e2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "دو مهره کیش می‌دهند ولی رخ e2 مهاجم پنهان است؛ شاه با زدن رخ نجات پیدا می‌کند.",
        "hints": [{"id": "h1", "text_fa": "همه مهاجم‌ها را پیدا کن، نه فقط واضح‌ترین را.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "1k2r3/8/8/3Q4/1b6/2P5/8/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "d1"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "سرباز c2 به c3 می‌رود ولی فیل b4 همچنان کیش می‌دهد، پس غیرقانونی است؛ شاه باید حرکت کند.",
        "hints": [{"id": "h1", "text_fa": "حرکت باید همه کیش‌ها را از بین ببرد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/6q1/7K w - - 0 1",
        "example": {"from": "h1", "to": "g2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "شاه در گوشه کیش است و تنها راه، زدن وزیر g2 است که مدافعی ندارد.",
        "hints": [{"id": "h1", "text_fa": "در گوشه صفحه راه‌های فرار کم است.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1",
        "example": {"from": "d4", "to": "d1"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "وزیر با d1 هم جلوی کیش رخ را می‌گیرد و هم به شاه سیاه کیش می‌دهد؛ ولی d8 جواب نیست چون کیش را باز نمی‌کند.",
        "hints": [{"id": "h1", "text_fa": "اول کیش خودت را باز کن، بعد به حمله فکر کن.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/5np1/8/4K3 w - - 0 1",
        "example": {"from": "e1", "to": "e2"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "اسب f3 کیش می‌دهد ولی سرباز g4 از آن دفاع می‌کند، پس نمی‌شود آن را زد؛ شاه به e2 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که دفاع می‌شود را نمی‌شود زد.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/8/4R1K1 b - - 0 1",
        "example": {"from": "e8", "to": "d8"},
        "prompt_fa": "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
        "explanation": "نوبت با سیاه است؛ رخ e1 کیش می‌دهد و شاه به d8 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت دقت کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
]


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition with raw python-chess.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses direct move generation, not the validator.
    """
    board = chess.Board(item["fen"])  # raises on invalid FEN
    if not board.is_check():
        raise ValueError(f"puzzle does not start in check: {item['fen']}")
    example = item["example"]
    move = chess.Move(
        chess.parse_square(example["from"]),
        chess.parse_square(example["to"]),
        promotion=PROMOTIONS.get(example.get("promotion")) if example.get("promotion") else None,
    )
    if move not in board.legal_moves:
        raise ValueError(f"example move not legal: {item['fen']} {example}")
    mover = board.turn
    board.push(move)
    try:
        king = board.king(mover)
        if king is None or board.is_attacked_by(not mover, king):
            raise ValueError(f"example move does not escape: {item['fen']} {example}")
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
            title_fa="رفع کیش",
            title_en="Get Out of Check",
            description="تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
            is_active=True,
            sort_order=5,
        )
        db.add(exercise)
        db.commit()
    elif exercise.title_fa != "رفع کیش":
        # Official Persian title is «رفع کیش» (never «فرار از کیش»).
        exercise.title_fa = "رفع کیش"
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"], "example": item["example"]}
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
        print(f"seeded {n} get-out-of-check puzzles")
    finally:
        db.close()
