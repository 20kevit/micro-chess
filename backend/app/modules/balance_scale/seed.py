"""Seed/demo puzzles for Balance Scale.

Run:  python -m app.modules.balance_scale.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry is independently verified (valid pieces, no kings, target
reachable by some bank combination) before insert; invalid entries fail
loudly instead of seeding a broken puzzle. Validation itself never
depends on one stored solution: any valid combination is accepted.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.balance_scale.validator import SLUG, VALUES, normalize_piece, total_value
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "با مهره‌های بانک، کفه چپ را با کفه راست برابر کن."

# Each entry: bank pieces, right-pan pieces, prompt, explanation, hints,
# rating. Difficulty rises gradually; answers are derived, never stored.
PUZZLES: list[dict] = [
    {
        "bank": ["P"],
        "right": ["P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "هر سرباز ۱ امتیاز دارد؛ یک سرباز با یک سرباز برابر است.",
        "hints": [{"id": "h1", "text_fa": "ارزش دو طرف را با هم مقایسه کن.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "bank": ["P", "P"],
        "right": ["P", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "دو سرباز می‌شود ۲ امتیاز؛ پس دو سرباز هم لازم است.",
        "hints": [{"id": "h1", "text_fa": "اول جمع سمت راست را حساب کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "bank": ["N", "B"],
        "right": ["N"],
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب ۳ امتیاز دارد؛ همان اسب بانک جواب است.",
        "hints": [{"id": "h1", "text_fa": "اسب چند امتیاز دارد؟", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "bank": ["N"],
        "right": ["B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب و فیل هر دو ۳ امتیاز دارند؛ پس با هم برابرند.",
        "hints": [{"id": "h1", "text_fa": "کدام دو مهره هم‌ارزش‌اند؟", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "bank": ["R", "P"],
        "right": ["R"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ ۵ امتیاز دارد؛ سرباز اضافه جواب را به‌هم می‌زند.",
        "hints": [{"id": "h1", "text_fa": "رخ چند امتیاز دارد؟", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "bank": ["Q", "N"],
        "right": ["Q"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر ۹ امتیاز دارد؛ بزرگ‌ترین مهره صفحه است.",
        "hints": [{"id": "h1", "text_fa": "وزیر از همه مهره‌ها ارزشمندتر است.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "bank": ["R", "P", "N"],
        "right": ["B", "B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۶ امتیاز دارد؛ رخ (۵) به‌علاوه سرباز (۱) می‌شود ۶.",
        "hints": [{"id": "h1", "text_fa": "کدام دو مهره با هم ۶ می‌شوند؟", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "bank": ["R", "P", "P", "N"],
        "right": ["N", "P", "P", "P", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۷ امتیاز دارد؛ رخ (۵) به‌علاوه دو سرباز (۲) می‌شود ۷.",
        "hints": [{"id": "h1", "text_fa": "اول جمع سمت راست را حساب کن: ۳+۱+۱+۱+۱.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "bank": ["B", "P", "N"],
        "right": ["P", "P", "P", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۴ امتیاز دارد؛ هم فیل+سرباز و هم اسب+سرباز درست است.",
        "hints": [{"id": "h1", "text_fa": "بیش از یک جواب درست وجود دارد.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "bank": ["N", "N", "P", "P", "R"],
        "right": ["R", "B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۸ امتیاز دارد؛ اسب+اسب+سرباز+سرباز یا رخ+اسب، هر دو درست‌اند.",
        "hints": [{"id": "h1", "text_fa": "ترکیب‌های مختلف را امتحان کن.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "bank": ["R", "B", "P"],
        "right": ["Q"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر به‌تنهایی ۹ امتیاز است؛ رخ (۵) + فیل (۳) + سرباز (۱) هم می‌شود ۹.",
        "hints": [{"id": "h1", "text_fa": "۹ را با سه مهره بساز.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "bank": ["R", "R"],
        "right": ["Q", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۱۰ امتیاز دارد؛ دو رخ می‌شود ۱۰.",
        "hints": [{"id": "h1", "text_fa": "دو مهره همسان هم می‌تواند جواب باشد.", "rating_cost": 10}],
        "rating": 1150.0,
    },
    {
        "bank": ["R", "R", "P", "P"],
        "right": ["Q", "B"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۱۲ امتیاز دارد؛ دو رخ و دو سرباز می‌شود ۱۲.",
        "hints": [{"id": "h1", "text_fa": "از مهره‌های بزرگ شروع کن.", "rating_cost": 10}],
        "rating": 1200.0,
    },
    {
        "bank": ["Q", "R", "B", "N", "P", "P"],
        "right": ["Q", "R"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۱۴ امتیاز دارد؛ وزیر+رخ یا وزیر+اسب+سرباز+سرباز، هر دو درست‌اند.",
        "hints": [{"id": "h1", "text_fa": "بانک شلوغ است؛ با دقت جمع بزن.", "rating_cost": 15}],
        "rating": 1300.0,
    },
    {
        "bank": ["Q", "B", "B", "N", "P", "P"],
        "right": ["Q", "R", "P"],
        "prompt_fa": PROMPT_FA,
        "explanation": "سمت راست ۱۵ امتیاز دارد؛ وزیر+فیل+اسب می‌شود ۱۵.",
        "hints": [{"id": "h1", "text_fa": "بزرگ‌ترین ترکیب ممکن را اول امتحان کن.", "rating_cost": 15}],
        "rating": 1350.0,
    },
]


def reachable(bank: list[str], target: int) -> bool:
    """Subset-sum check: some bank sub-multiset totals exactly target."""
    possible = {0}
    for piece in bank:
        value = VALUES[piece]
        possible |= {total + value for total in possible if total + value <= target}
    return target in possible


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Does not call the validator.
    """
    bank = item.get("bank")
    right = item.get("right")
    if not isinstance(bank, list) or not isinstance(right, list) or not bank or not right:
        raise ValueError(f"puzzle needs non-empty bank and right lists: {item}")
    clean_bank = [normalize_piece(p) for p in bank]
    clean_right = [normalize_piece(p) for p in right]
    if any(p is None for p in clean_bank + clean_right):
        raise ValueError(f"invalid piece (kings forbidden): {item}")
    target = total_value([p for p in clean_right if p is not None])
    if target <= 0:
        raise ValueError(f"target must be positive: {item}")
    if not reachable([p for p in clean_bank if p is not None], target):
        raise ValueError(f"target unreachable from bank: {item}")


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="ترازو",
            title_en="Balance Scale",
            description="با مهره‌های بانک، کفه چپ را با کفه راست برابر کن.",
            is_active=True,
            sort_order=10,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"bank": item["bank"], "right": item["right"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=None,
            position_json={"bank": item["bank"], "right": item["right"]},
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
        print(f"seeded {n} balance-scale puzzles")
    finally:
        db.close()
