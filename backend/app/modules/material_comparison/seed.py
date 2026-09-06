"""Seed/demo puzzles for Material Comparison.

Run:  python -m app.modules.material_comparison.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified (valid pieces, no kings, sensible
left/right/equal distribution) before insert; invalid entries fail loudly
instead of seeding a broken puzzle. Validation itself always recomputes
both totals from the stored lists.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.material_comparison.validator import SLUG, VALUES, normalize_piece
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "کدام طرف سنگین‌تر است؟"

# Each entry: left pieces, right pieces, prompt, explanation, hints, rating.
# Roughly 20% equal; the rest split between left- and right-heavy.
PUZZLES: list[dict] = [
    {
        "left": ["R"],
        "right": ["P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ ۵ امتیاز و سرباز ۱ امتیاز دارد؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "ارزش هر مهره را جداگانه حساب کن.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "left": ["Q"],
        "right": ["P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر ۹ امتیاز و سرباز ۱ امتیاز دارد؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌های بزرگ را مقایسه کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "left": ["N", "N"],
        "right": ["P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "دو اسب می‌شود ۶ امتیاز در برابر ۱ امتیاز سرباز؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "مهره‌های همسان را با هم جمع بزن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "left": ["Q"],
        "right": ["N", "B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر به‌تنهایی ۹ امتیاز است و اسب+فیل می‌شود ۶؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "اسب و فیل هر دو ۳ امتیاز دارند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "left": ["R", "R"],
        "right": ["Q"],
        "prompt_fa": PROMPT_FA,
        "explanation": "دو رخ می‌شود ۱۰ امتیاز در برابر ۹ امتیاز وزیر؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "رخ ۵ امتیاز دارد؛ دو تا می‌شود ۱۰.", "rating_cost": 10}],
        "rating": 900.0,
    },
    {
        "left": ["Q", "N"],
        "right": ["P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر و اسب می‌شود ۱۲ امتیاز در برابر ۱ امتیاز؛ پس سمت چپ سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "یک وزیر به‌تنهایی از چند سرباز بیشتر است.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "left": ["P"],
        "right": ["R"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز ۱ امتیاز و رخ ۵ امتیاز دارد؛ پس سمت راست سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "ارزش هر مهره را جداگانه حساب کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "left": ["N"],
        "right": ["Q"],
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب ۳ امتیاز و وزیر ۹ امتیاز دارد؛ پس سمت راست سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌های بزرگ را مقایسه کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "left": ["B", "P"],
        "right": ["R", "B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت چپ ۴ و سمت راست ۸ امتیاز دارد؛ پس سمت راست سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "هر طرف را قدم‌به‌قدم جمع بزن.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "left": ["P", "P", "P"],
        "right": ["R"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سه سرباز فقط ۳ امتیاز می‌شود ولی یک رخ ۵ امتیاز دارد؛ تعداد بیشتر همیشه به معنی سنگین‌تر نیست.",
        "hints": [{"id": "h1", "text_fa": "تعداد مهره‌ها گولت نزند؛ ارزش‌ها را جمع بزن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "left": ["N"],
        "right": ["B", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب به‌تنهایی ۳ امتیاز است ولی فیل+سرباز می‌شود ۴؛ پس سمت راست سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "اسب و فیل هم‌ارزش‌اند، ولی سرباز اضافه ورق را برمی‌گرداند.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "left": ["P", "P", "P", "N"],
        "right": ["Q"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سه سرباز و یک اسب می‌شود ۶ امتیاز ولی یک وزیر به‌تنهایی ۹ امتیاز دارد؛ پس سمت راست سنگین‌تر است.",
        "hints": [{"id": "h1", "text_fa": "یک وزیر از چند مهره کوچک بیشتر می‌ارزد.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "left": ["Q"],
        "right": ["R", "B", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر ۹ امتیاز است و رخ+فیل+سرباز هم می‌شود ۹؛ پس دو طرف مساوی‌اند.",
        "hints": [{"id": "h1", "text_fa": "۹ را به دو شکل مختلف بساز.", "rating_cost": 10}],
        "rating": 1150.0,
    },
    {
        "left": ["R", "N"],
        "right": ["B", "N", "P", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "هر دو طرف ۸ امتیاز دارند؛ پس مساوی‌اند.",
        "hints": [{"id": "h1", "text_fa": "طرف شلوغ‌تر را یکی‌یکی جمع بزن.", "rating_cost": 15}],
        "rating": 1250.0,
    },
    {
        "left": ["N", "P"],
        "right": ["B", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "هر دو طرف ۴ امتیاز دارند چون اسب و فیل هم‌ارزش‌اند؛ پس مساوی‌اند.",
        "hints": [{"id": "h1", "text_fa": "کدام دو مهره هم‌ارزش‌اند؟", "rating_cost": 10}],
        "rating": 1200.0,
    },
]


def verify_puzzle(item: dict) -> str:
    """Independently verify one puzzle definition; return its expected answer.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Does not call the validator.
    """
    left = item.get("left")
    right = item.get("right")
    if not isinstance(left, list) or not isinstance(right, list) or not left or not right:
        raise ValueError(f"puzzle needs non-empty left and right lists: {item}")
    clean_left = [normalize_piece(p) for p in left]
    clean_right = [normalize_piece(p) for p in right]
    if any(p is None for p in clean_left + clean_right):
        raise ValueError(f"invalid piece (kings forbidden): {item}")
    left_value = sum(VALUES[p] for p in clean_left if p is not None)
    right_value = sum(VALUES[p] for p in clean_right if p is not None)
    if left_value > right_value:
        return "left"
    if right_value > left_value:
        return "right"
    return "equal"


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    distribution: dict[str, int] = {}
    for item in PUZZLES:
        expected = verify_puzzle(item)
        distribution[expected] = distribution.get(expected, 0) + 1
    if distribution.get("equal", 0) < 2 or distribution.get("left", 0) < 4 or distribution.get("right", 0) < 4:
        raise ValueError(f"answer distribution not sensible: {distribution}")

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="کدام طرف سنگین‌تر است؟",
            title_en="Which Side is Heavier?",
            description="بگو کدام طرف مهره‌های ارزشمندتری دارد.",
            is_active=True,
            sort_order=9,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"left": item["left"], "right": item["right"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=None,
            position_json={"left": item["left"], "right": item["right"]},
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
        print(f"seeded {n} heavier-side puzzles")
    finally:
        db.close()
