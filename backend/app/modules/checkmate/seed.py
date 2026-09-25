"""Seed/demo puzzles for Is it Checkmate?.

Run:  python -m app.modules.checkmate.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry carries its expected classification, independently verified
with raw python-chess (is_check/is_checkmate on the FEN, never the
validator) before insert; invalid entries fail loudly instead of seeding
a broken puzzle.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.checkmate.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_IMPORTED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle

PROMPT_FA = "وضعیت طرفی که نوبت حرکت با اوست چیست؟"

# Each entry: fen, expected state, prompt, explanation, hints, rating.
# Ordered easy → hard: obvious mates, obvious checks, quiet positions,
# then double checks, captures, blocks and the stalemate trap.
PUZZLES: list[dict] = [
    {
        "fen": "7k/6Q1/7K/8/8/8/8/8 b - - 0 1",
        "answer": "checkmate",
        "prompt_fa": PROMPT_FA,
        "explanation": "مات. شاه در کیش است و هیچ حرکت قانونی برای خروج از کیش ندارد.",
        "hints": [{"id": "h1", "text_fa": "اول ببین شاه کیش است یا نه.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "k7/1Q6/2K5/8/8/8/8/8 b - - 0 1",
        "answer": "checkmate",
        "prompt_fa": PROMPT_FA,
        "explanation": "مات. وزیر خانه‌های فرار را بسته و شاه در کیش است.",
        "hints": [{"id": "h1", "text_fa": "خانه‌های اطراف شاه را یکی‌یکی بررسی کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "k7/8/K7/3B4/8/8/8/1Q6 b - - 0 1",
        "answer": "checkmate",
        "prompt_fa": PROMPT_FA,
        "explanation": "مات. کیش دوبل است و شاه هیچ خانه امنی ندارد.",
        "hints": [{"id": "h1", "text_fa": "بشمار چند مهره کیش می‌دهند.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "3Q2k1/5ppp/4N3/8/8/8/8/K7 b - - 0 1",
        "answer": "checkmate",
        "prompt_fa": PROMPT_FA,
        "explanation": "مات. وزیر کیش می‌دهد، سربازها راه فرار را بسته‌اند و گرفتن وزیر ممکن نیست.",
        "hints": [{"id": "h1", "text_fa": "آیا مهره کیش‌دهنده را می‌شود زد؟", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1",
        "answer": "checkmate",
        "prompt_fa": PROMPT_FA,
        "explanation": "مات. وزیر سیاه به شاه سفید کیش داده و هیچ دفاعی وجود ندارد.",
        "hints": [{"id": "h1", "text_fa": "این دام معروف گشایشی را می‌شناسی؟", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "k3r3/8/8/8/8/8/8/4K3 w - - 0 1",
        "answer": "check",
        "prompt_fa": PROMPT_FA,
        "explanation": "کیش. رخ کیش می‌دهد ولی شاه می‌تواند حرکت کند.",
        "hints": [{"id": "h1", "text_fa": "اگر شاه کیش است، دنبال راه فرار بگرد.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/8/5n2/6P1/4K3 w - - 0 1",
        "answer": "check",
        "prompt_fa": PROMPT_FA,
        "explanation": "کیش. اسب کیش می‌دهد ولی می‌شود آن را زد.",
        "hints": [{"id": "h1", "text_fa": "آیا مهاجم را می‌شود گرفت؟", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/1b6/8/2P5/4K3 w - - 0 1",
        "answer": "check",
        "prompt_fa": PROMPT_FA,
        "explanation": "کیش. فیل کیش می‌دهد ولی می‌شود جلوی آن مهره گذاشت.",
        "hints": [{"id": "h1", "text_fa": "آیا می‌شود جلوی خط حمله مهره گذاشت؟", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "k3r3/8/8/8/1b6/8/8/4K3 w - - 0 1",
        "answer": "check",
        "prompt_fa": PROMPT_FA,
        "explanation": "کیش. دو مهره حمله می‌کنند ولی شاه هنوز یک خانه فرار دارد.",
        "hints": [{"id": "h1", "text_fa": "حتی با دو مهاجم هم ممکن است راه فرار باشد.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1",
        "answer": "check",
        "prompt_fa": PROMPT_FA,
        "explanation": "کیش. وزیر از خانه مجاور کیش می‌دهد ولی شاه می‌تواند آن را بزند.",
        "hints": [{"id": "h1", "text_fa": "شاه خودش هم می‌تواند مهاجم را بزند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "answer": "not_check",
        "prompt_fa": PROMPT_FA,
        "explanation": "بدون کیش. شاه سیاه در کیش نیست و بازی عادی ادامه دارد.",
        "hints": [{"id": "h1", "text_fa": "اول ببین شاه کیش است یا نه.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "r3k3/8/8/8/8/8/8/R3K3 w - - 0 1",
        "answer": "not_check",
        "prompt_fa": PROMPT_FA,
        "explanation": "بدون کیش. هیچ‌کدام از شاه‌ها زیر ضربه نیستند.",
        "hints": [{"id": "h1", "text_fa": "نبودن کیش هم یک جواب درست است.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/8/8/7n/8/4K3 w - - 0 1",
        "answer": "not_check",
        "prompt_fa": PROMPT_FA,
        "explanation": "بدون کیش. اسب نزدیک شاه است ولی به آن کیش نمی‌دهد.",
        "hints": [{"id": "h1", "text_fa": "نزدیک بودن مهاجم یعنی کیش بودن؟", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/2b5/8/8/8/4K3 w - - 0 1",
        "answer": "not_check",
        "prompt_fa": PROMPT_FA,
        "explanation": "بدون کیش. فیل به سمت شاه نشانه رفته ولی به آن نرسیده است.",
        "hints": [{"id": "h1", "text_fa": "خط حمله را تا آخر دنبال کن.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
        "answer": "not_check",
        "prompt_fa": PROMPT_FA,
        "explanation": "بدون کیش. شاه در کیش نیست، اما هیچ حرکت قانونی وجود ندارد؛ این وضعیت پات است، نه مات.",
        "hints": [{"id": "h1", "text_fa": "نبودن حرکت قانونی همیشه به معنی مات نیست.", "rating_cost": 10}],
        "rating": 1100.0,
    },
]


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition with raw python-chess.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses direct is_check/is_checkmate calls
    plus a kings-present guard, not the validator.
    """
    board = chess.Board(item["fen"])  # raises on invalid FEN
    if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
        raise ValueError(f"puzzle needs both kings: {item['fen']}")
    if board.is_checkmate():
        expected = "checkmate"
    elif board.is_check():
        expected = "check"
    else:
        expected = "not_check"
    if expected != item["answer"]:
        raise ValueError(f"classification mismatch: {item['fen']} computed {expected}")


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="آیا مات است؟",
            title_en="Is it Checkmate?",
            description="بگو وضعیت طرفی که نوبت اوست چیست.",
            is_active=True,
            sort_order=12,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"]}
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
        print(f"seeded {n} is-checkmate puzzles")
    finally:
        db.close()
