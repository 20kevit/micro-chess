"""Seed/demo puzzles for Blindfold Calculation (Mate in 1 only).

Run:  python -m app.modules.blindfold_calculation.seed
Idempotent: skips when puzzles for the slug already exist.

Security: the FEN lives ONLY in server-side answer_json. The Puzzle.fen
column stays NULL and position_json carries just the Persian description,
side to move and mode -- so the normal puzzle endpoint never leaks the
position, the expected SAN, or any mate flags before submission.

Every puzzle is independently verified (raw python-chess legal-move loop,
never the production validator): the FEN must parse and yield exactly one
mating move, and the stored example SAN must be that move.
"""

import chess
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.blindfold_calculation.description import describe_position, side_to_move
from app.modules.blindfold_calculation.validator import SLUG
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle

# Each entry: fen, prompt, explanation (conceptual, no destination squares),
# hints (never reveal the move), rating.
PUZZLES: list[dict] = [
    {
        "fen": "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "شاه سیاه در ردیف آخر پشت سربازهای خودش گیر کرده است؛ رخی که وارد ردیف آخر شود و راه فرار را ببندد مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "به دنبال حرکتی باش که همزمان به شاه کیش بدهد و تمام راه‌های فرار را ببندد.", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "fen": "6k1/6pp/6Q1/8/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "وزیر از دور به شاه نزدیک می‌شود؛ وقتی همه خانه‌های اطراف شاه بسته یا زیر ضربه باشند، کیش وزیر مات است.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "وزیر دوربرد است؛ خانه‌ای را پیدا کن که از آنجا هم کیش بدهد هم راه فرار را ببندد.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "fen": "6rk/6pp/8/4N3/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "شاه سیاه بین مهره‌های خودش خفه شده است؛ اسب می‌پرد و کیش می‌دهد و شاه جایی برای فرار ندارد.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب می‌پرد؛ پرشی را پیدا کن که به شاه کیش بدهد.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "1k6/1p6/1P6/2Q5/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "شاه سیاه در گوشه گیر افتاده است؛ وزیر از ستون کناری وارد می‌شود و مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "به دنبال حرکتی باش که همزمان به شاه کیش بدهد و تمام راه‌های فرار را ببندد.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "fen": "r5k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "گوشه صفحه برای شاه حریف تله است؛ رخی که ستون گوشه را بگیرد و زدن آن ممکن نباشد مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "رخ فقط مستقیم می‌رود؛ ستونی را پیدا کن که شاه را کیش‌مات کند.", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "fen": "7k/6pp/5R2/6N1/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "رخ و اسب با هم کار می‌کنند؛ رخ وارد ردیف آخر می‌شود و اسب راه برگشت شاه را می‌بندد.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "رخ را به ردیف آخر ببر و ببین اسب کدام خانه فرار را بسته است.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "fen": "k7/p7/8/8/B7/8/8/1R4K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "فیل از روی قطر به شاه گوشه کیش می‌دهد؛ وقتی رخ خانه‌های کنار شاه را بسته باشد، این کیش مات است.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل فقط روی قطر می‌رود؛ قطری را پیدا کن که به شاه برسد.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
    {
        "fen": "6bk/6pp/5P2/7N/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "سرباز هم می‌تواند مات کند؛ وقتی سرباز جلو برود و شاه را کیش بدهد و مهره‌ای از آن دفاع کند، شاه راهی ندارد.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "سرباز فقط یک خانه جلو یا مورب می‌زند؛ کدام حرکتش کیش می‌دهد؟", "rating_cost": 10},
        ],
        "rating": 1050.0,
    },
    {
        "fen": "6k1/8/8/8/8/3b1b2/4rPPP/6K1 b - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده سیاه را پیدا کن.",
        "explanation": "این بار نوبت سیاه است؛ شاه سفید در ردیف آخر گیر کرده و رخ سیاه با بستن راه فرار مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "به نوبت حرکت دقت کن: این بار سیاه مات می‌کند.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "fen": "6k1/6pp/8/8/2B5/8/5PPP/1R4K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "رخ از ستون کناری بالا می‌رود؛ فیل خانه‌های فرار شاه را از دور بسته است.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "رخ را به ردیف آخر ببر و ببین کدام مهره راه فرار را بسته است.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "3qkb2/3ppp2/8/4N2Q/8/8/5PPP/4K3 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "وزیر مهره حریف را می‌زند و کیش می‌دهد؛ چون اسب از وزیر دفاع می‌کند، شاه نمی‌تواند آن را بگیرد.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "زدن هم یک حرکت است؛ مهره‌ای را بزن که بعد از زدن، کسی نتواند پس بگیرد.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "fen": "kr6/pp6/8/3N4/8/8/8/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "شاه سیاه در گوشه دیگر صفحه هم بین مهره‌های خودش گیر کرده است؛ پرش اسب مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب می‌پرد؛ پرشی را پیدا کن که به شاه کیش بدهد.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "7k/6pp/5K2/6Q1/8/8/8/8 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "شاه سفید خودش نزدیک شاه سیاه آمده و از وزیر دفاع می‌کند؛ زدن سربازی که شاه را کیش‌مات کند جواب است.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "مهره‌ای که شاه خودی از آن دفاع می‌کند را جلو ببر.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
    {
        "fen": "k7/ppp5/1Q6/8/8/8/5PPP/1R4K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "وزیر سرباز جلوی شاه را می‌زند؛ چون رخ از وزیر دفاع می‌کند، شاه نمی‌تواند فرار کند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "زدن هم یک حرکت است؛ مهره‌ای را بزن که بعد از زدن، کسی نتواند پس بگیرد.", "rating_cost": 10},
        ],
        "rating": 1050.0,
    },
    {
        "fen": "7k/3p2pp/8/5Q2/8/8/5PPP/6K1 w - - 0 1",
        "prompt_fa": "بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
        "explanation": "وزیر از وسط صفحه راه دوری می‌آید؛ مهم این است که بعد از کیش، هیچ خانه فراری نماند.",
        "hints": [
            {"id": "h1", "text_fa": "اول جای شاه حریف و خانه‌های فرار اطرافش را در ذهنت پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "وزیر دوربرد است؛ خانه‌ای را پیدا کن که از آنجا هم کیش بدهد هم راه فرار را ببندد.", "rating_cost": 10},
        ],
        "rating": 1100.0,
    },
]


def _independent_mates(fen: str) -> list[str]:
    """Raw mate search with python-chess only (never the validator)."""
    board = chess.Board(fen)
    mates: list[str] = []
    for move in board.legal_moves:
        san = board.san(move)
        board.push(move)
        try:
            if board.is_checkmate():
                mates.append(san)
        finally:
            board.pop()
    return sorted(mates)


def verify_puzzle(item: dict) -> str:
    """Fail loudly unless the FEN has exactly one mate; return its SAN."""
    mates = _independent_mates(item["fen"])
    if len(mates) != 1:
        raise ValueError(f"expected exactly 1 mate-in-1, got {len(mates)}: {item['fen']} -> {mates}")
    # Description must generate without errors (blindfold suitability).
    describe_position(item["fen"])
    return mates[0]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="محاسبه‌ی ذهنی",
            title_en="Blindfold Calculation",
            description="بدون دیدن صفحه، حرکت مات‌کننده را پیدا کن.",
            is_active=True,
            sort_order=14,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        example = verify_puzzle(item)
        answer = {"fen": item["fen"], "example": example, "mate_count": 1}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=None,
            position_json={
                "description_fa": describe_position(item["fen"]),
                "side_to_move": side_to_move(item["fen"]),
                "mode": "mate-in-1",
            },
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
        print(f"seeded {n} blindfold-calculation puzzles")
    finally:
        db.close()
