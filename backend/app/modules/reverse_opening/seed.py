"""Seed/demo puzzles for Reverse Opening.

Run:  python -m app.modules.reverse_opening.seed
Idempotent: skips when puzzles for the slug already exist.

Target positions are GENERATED from the move sequences (never hand-typed),
so stored targets always match their canonical line. Verification is fully
independent (raw python-chess, never the production validator): every move
must be legal from the standard start, every target must differ from the
start, no two targets may coincide, and hints must not contain solution
text.

Security: answer_json (start/target/solutions) is server-only. The visible
position_json carries the start and target FENs (both boards must render)
plus opening context -- but never the solution sequence.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.reverse_opening.description import describe_opening
from app.modules.reverse_opening.validator import (
    SLUG,
    START_FEN,
    play_sequence,
    position_key,
)
from app.modules.puzzles.models import Puzzle

# Each entry: canonical UCI line from the standard start, Persian opening
# name (metadata only, never the answer), explanation, hints, rating.
PUZZLES: list[dict] = [
    {
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"],
        "opening_fa": "بازی ایتالیایی",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید مرکز را با پیاده‌ها می‌گیرد و اسب و فیل را به خانه‌های فعال می‌آورد؛ هر دو فیل به سمت شاه حریف نگاه می‌کنند.",
        "hints": [
            {"id": "h1", "text_fa": "به حرکت اول سفید فکر کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "حرکت اول با پیشروی پیاده شاه آغاز می‌شود.", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6"],
        "opening_fa": "روئی لوپز",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "فیل سفید با بیرون آمدن و برگشتن، فشار روی اسب مدافع مرکز را حفظ می‌کند؛ سیاه با پیاده کناری و اسب جواب می‌دهد.",
        "hints": [
            {"id": "h1", "text_fa": "به حرکت اول سفید فکر کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل سفید دو بار حرکت می‌کند: بیرون می‌آید و برمی‌گردد.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "moves": ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"],
        "opening_fa": "دفاع سیسیلی",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سیاه با پیاده کناری به مرکز سفید حمله می‌کند و بعد پیاده‌ها تعویض می‌شوند؛ اسب‌ها به خانه‌های مرکزی می‌آیند.",
        "hints": [
            {"id": "h1", "text_fa": "سیاه در حرکت اول سراغ پیاده شاه نمی‌رود.", "rating_cost": 5},
            {"id": "h2", "text_fa": "در مرکز پیاده‌ها با هم تعویض می‌شوند.", "rating_cost": 10},
        ],
        "rating": 1100.0,
    },
    {
        "moves": ["e2e4", "e7e6", "d2d4", "d7d5", "b1c3", "f8b4", "e4e5"],
        "opening_fa": "دفاع فرانسوی",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید مرکز را می‌بندد و با پیشروی پیاده، فیل حریف را محدود می‌کند؛ اسب از پیاده دفاع می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "سفید مرکز را با پیاده‌ها قفل می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل سیاه بیرون می‌آید و اسب را آچمز می‌کند.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "moves": ["e2e4", "c7c6", "d2d4", "d7d5", "e4d5", "c6d5", "g1f3"],
        "opening_fa": "دفاع کاروکان",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "پیاده‌های مرکزی تعویض می‌شوند و اسب سفید به مرکز می‌آید؛ ساختار ساده و محکم است.",
        "hints": [
            {"id": "h1", "text_fa": "سیاه با پیاده کناری شروع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "در مرکز پیاده‌ها با هم تعویض می‌شوند.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "moves": ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6", "c1g5", "f8e7"],
        "opening_fa": "گامبی وزیر",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید با پیاده کناری به مرکز حمله می‌کند؛ سیاه مرکز را نگه می‌دارد و سوارها بیرون می‌آیند.",
        "hints": [
            {"id": "h1", "text_fa": "سفید با پیاده وزیر شروع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل سفید بیرون می‌آید و اسب حریف را آچمز می‌کند.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "moves": ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7", "e2e4", "d7d6"],
        "opening_fa": "دفاع هندی شاه",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سیاه اجازه می‌دهد سفید مرکز را بگیرد و بعد از جناحین به آن حمله می‌کند؛ فیل به خانه بلند برمی‌گردد.",
        "hints": [
            {"id": "h1", "text_fa": "سفید با پیاده وزیر شروع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "سیاه فیل را به طولانی‌ترین قطر می‌آورد.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4", "e5d4", "f3d4"],
        "opening_fa": "بازی اسکاتلندی",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید زود مرکز را باز می‌کند و پیاده‌ها تعویض می‌شوند؛ اسب به مرکز برمی‌گردد.",
        "hints": [
            {"id": "h1", "text_fa": "به حرکت اول سفید فکر کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "سفید زودتر از معمول پیاده وزیر را جلو می‌آورد.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "b1c3", "g8f6", "f1b5", "f8b4"],
        "opening_fa": "شروع چهار اسب",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "هر چهار اسب بیرون می‌آیند و بعد هر دو فیل؛ بازی متقارن و آموزشی است.",
        "hints": [
            {"id": "h1", "text_fa": "هر دو طرف اسب‌هایشان را بیرون می‌آورند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "بعد از اسب‌ها، نوبت فیل‌هاست.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "moves": ["d2d4", "d7d5", "c1f4", "g8f6", "e2e3", "e7e6", "g1f3", "c7c5"],
        "opening_fa": "سیستم لندن",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "فیل سفید زود بیرون می‌آید و ساختار محکم می‌ماند؛ سیاه از جناح به مرکز فشار می‌آورد.",
        "hints": [
            {"id": "h1", "text_fa": "سفید با پیاده وزیر شروع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل سفید قبل از بستن زنجیره پیاده‌ای بیرون می‌آید.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "moves": ["e2e4", "e7e5", "g1f3", "g8f6", "f3e5", "d7d6", "e5f3", "f6e4"],
        "opening_fa": "دفاع پتروف",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "اسب‌ها به مرکز می‌آیند و برمی‌گردند؛ هر دو طرف مراقب پیاده‌های مرکزی هستند.",
        "hints": [
            {"id": "h1", "text_fa": "به حرکت اول سفید فکر کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب سیاه هم مثل اسب سفید به مرکز می‌آید.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "moves": ["e2e4", "e7e5", "b1c3", "g8f6", "f2f4"],
        "opening_fa": "شروع وینی",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید اول اسب را بیرون می‌آورد و بعد با پیاده جناحی به مرکز حمله می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "سفید با اسب شروع می‌کند، نه با پیاده.", "rating_cost": 5},
            {"id": "h2", "text_fa": "آخرین حرکت یک پیاده جناحی است.", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "moves": ["e2e4", "c7c5", "c2c3", "d7d5", "e4d5", "d8d5", "d2d4"],
        "opening_fa": "سیسیلی آلاپین",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید با پیاده کناری مرکز محکمی می‌سازد؛ وزیر سیاه زود بیرون می‌آید و سفید با پیاده به آن حمله می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "سیاه در حرکت اول سراغ پیاده شاه نمی‌رود.", "rating_cost": 5},
            {"id": "h2", "text_fa": "وزیر سیاه زود وارد بازی می‌شود.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "moves": ["e2e4", "c7c6", "d2d4", "d7d5", "e4e5", "c8f5", "g1f3", "e7e6"],
        "opening_fa": "کاروکان پیشرفته",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید با پیشروی پیاده فضا می‌گیرد؛ سیاه فیل را بیرون نگه می‌دارد و زنجیره را کامل می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "سیاه با پیاده کناری شروع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "پیاده سفید از زنجیره جلو می‌زند.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "b2b4", "c5b4", "c2c3"],
        "opening_fa": "گامبی اوانز",
        "prompt_fa": "حرکت‌هایی را که به این وضعیت رسیده‌اند بازسازی کن.",
        "explanation": "سفید پیاده جناحی را قربانی می‌دهد تا فیل حریف را بکشد و بعد با پیاده به آن حمله کند.",
        "hints": [
            {"id": "h1", "text_fa": "به حرکت اول سفید فکر کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "سفید یک پیاده را برای سرعت قربانی می‌دهد.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
]


def verify_puzzle(item: dict) -> str:
    """Independently verify one puzzle; return its generated target FEN.

    Fails loudly unless: every move is legal from the standard start, the
    generated target differs from the start, and hints carry no solution
    text. Targets are always generated, never hand-typed.
    """
    board = play_sequence(START_FEN, item["moves"])  # raises on bad input
    target_fen = board.fen()
    if position_key(target_fen) == position_key(START_FEN):
        raise ValueError(f"target equals start: {item['moves']}")
    for hint in item["hints"]:
        for uci in item["moves"]:
            if uci in hint["text_fa"]:
                raise ValueError(f"hint leaks move {uci}")
    describe_opening(target_fen, item["opening_fa"])
    return target_fen


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    targets = [verify_puzzle(item) for item in PUZZLES]
    if len(set(position_key(fen) for fen in targets)) != len(targets):
        raise ValueError("duplicate target positions")

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="گشایش معکوس",
            title_en="Reverse Opening",
            description="ترتیب حرکت‌های گشایش را برعکس بچین.",
            is_active=True,
            sort_order=16,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item, target_fen in zip(PUZZLES, targets):
        answer = {
            "start_fen": START_FEN,
            "target_fen": target_fen,
            "solutions": [list(item["moves"])],
        }
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=target_fen,
            position_json={
                "start_fen": START_FEN,
                "target_fen": target_fen,
                "mode": "reconstruct",
                "opening_fa": item["opening_fa"],
                "description_fa": describe_opening(target_fen, item["opening_fa"]),
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
        print(f"seeded {n} reverse-opening puzzles")
    finally:
        db.close()
