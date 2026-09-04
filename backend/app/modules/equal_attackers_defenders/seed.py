"""Seed/demo puzzles for Equal Attackers & Defenders.

Run:  python -m app.modules.equal_attackers_defenders.seed
Idempotent: skips when puzzles for the slug already exist.
Answers are computed from FEN via balanced_squares, so they are
verifiable; tests recompute them independently with python-chess.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.equal_attackers_defenders.validator import SLUG, balanced_squares
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "مهره‌هایی که تعداد مهاجم‌ها و مدافع‌هایشان برابر است را انتخاب کن."

# Each entry: fen, explanation (teaches the actual counts), hints, rating.
# Answers are derived from the FEN at seed time.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز e4 را یک مهره (اسب f6) می‌زند و یک مهره (سرباز d3) از آن دفاع می‌کند؛ یک در برابر یک، پس هدف است.",
        "hints": [{"id": "h1", "text_fa": "مهاجم‌ها را بشمار، بعد مدافع‌ها را.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "fen": "4k3/8/8/2b1p3/3N4/2P1P3/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب d4 را دو مهره (فیل c5 و سرباز e5) می‌زنند و دو مهره (سربازهای c3 و e3) از آن دفاع می‌کنند؛ دو در برابر دو.",
        "hints": [{"id": "h1", "text_fa": "اسب وسط صفحه را خوب بررسی کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "3rk3/8/8/2b1p3/3Q4/2P1P3/8/3RK3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر d4 سه مهاجم (رخ d8، فیل c5، سرباز e5) و سه مدافع (سربازهای c3 و e3 و رخ d1) دارد. رخ d8 هم یک در برابر یک است. دقت کن رخ d1 زیر ضربه نیست چون وزیر راه رخ سیاه را بسته است.",
        "hints": [{"id": "h1", "text_fa": "مانع جلوی حمله را هم در نظر بگیر.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4k3/8/5n2/8/4P2q/3P4/8/5K2 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز e4 دو مهاجم (اسب f6 و وزیر h4) ولی فقط یک مدافع (سرباز d3) دارد؛ مهاجم بیشتر یعنی هدف نیست.",
        "hints": [{"id": "h1", "text_fa": "اول مهاجم‌ها را کامل بشمار.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "4k3/4p3/3p4/4P3/3P4/5N2/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز e5 فقط یک مهاجم (سرباز d6) ولی دو مدافع (سرباز d4 و اسب f3) دارد؛ مدافع بیشتر یعنی هدف نیست. خود سرباز d6 یک در برابر یک است.",
        "hints": [{"id": "h1", "text_fa": "مهره سیاه هم می‌تواند هدف باشد.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/p7/1P6/8/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز b4 زیر ضربه است ولی هیچ مدافعی ندارد؛ بدون مدافع، تساوی معنا ندارد.",
        "hints": [{"id": "h1", "text_fa": "صفر در برابر یک، تساوی نیست.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/1P6/2P1K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز c3 مدافع دارد ولی هیچ مهاجمی ندارد؛ بدون مهاجم، هدف نیست.",
        "hints": [{"id": "h1", "text_fa": "اول ببین اصلاً حمله‌ای هست یا نه.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/8/8/8/5P2/4K1N1 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "نه حمله‌ای هست نه دفاعی؛ پس چیزی انتخاب نکن.",
        "hints": [{"id": "h1", "text_fa": "صفحه آرام هم جواب خالی دارد.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "fen": "4k3/8/8/5b2/3pQ3/3P4/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر e4 را فقط فیل f5 می‌زند و فقط سرباز d3 از آن دفاع می‌کند؛ یک در برابر یک.",
        "hints": [{"id": "h1", "text_fa": "حمله مورب فیل را دنبال کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/6p1/5q2/6B1/3N4/2P5/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب d4 را وزیر f6 می‌زند و سرباز c3 دفاع می‌کند. خود وزیر f6 را فیل g5 می‌زند و سرباز g7 دفاع می‌کند؛ هر دو یک در برابر یک‌اند.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم می‌زند و هم ممکن است هدف باشد.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "4k3/8/8/8/4P1Nq/8/8/5K2 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر h4 به نظر می‌رسد سرباز e4 را می‌زند، ولی اسب g4 راه را بسته است؛ پس e4 اصلاً مهاجمی ندارد.",
        "hints": [{"id": "h1", "text_fa": "مانع، حمله را قطع می‌کند.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/8/8/1N6/3k4/2P5/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز c2 زیر ضربه شاه سیاه است و اسب b4 از آن دفاع می‌کند؛ شاه هم مهاجم حساب می‌شود.",
        "hints": [{"id": "h1", "text_fa": "شاه هم می‌تواند حمله و دفاع کند.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "3rk3/8/8/2b5/3Q4/2P5/3P4/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر d4 دو مهاجم دارد ولی فقط سرباز c3 از آن دفاع می‌کند، چون سرباز d2 راه رخ d1 را بسته است؛ دو در برابر یک یعنی هدف نیست. فقط رخ d8 یک در برابر یک است.",
        "hints": [{"id": "h1", "text_fa": "مدافعی که راهش بسته است، مدافع نیست.", "rating_cost": 10}],
        "rating": 1200.0,
    },
    {
        "fen": "4k3/8/8/2n5/4P3/3B4/8/4K3 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز e4 را اسب c5 می‌زند و فیل d3 از آن دفاع می‌کند؛ حمله اسب را با دقت بشمار.",
        "hints": [{"id": "h1", "text_fa": "حرکت اسب را قدم‌به‌قدم دنبال کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "4k3/8/8/8/8/1N1r4/2P5/5K2 w - - 0 1",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب b3 زیر ضربه رخ d3 است و سرباز c2 از آن دفاع می‌کند؛ یک در برابر یک در گوشه صفحه.",
        "hints": [{"id": "h1", "text_fa": "گوشه‌ها را هم بررسی کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
]


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="برابری حمله‌کننده‌ها و مدافع‌ها",
            title_en="Equal Attackers & Defenders",
            description="مهره‌هایی که مهاجم‌ها و مدافع‌هایشان برابر است را پیدا کن.",
            is_active=True,
            sort_order=4,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        squares = balanced_squares(item["fen"])
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
        print(f"seeded {n} equal-attackers-defenders puzzles")
    finally:
        db.close()
