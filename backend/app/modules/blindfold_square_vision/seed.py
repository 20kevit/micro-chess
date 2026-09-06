"""Seed/demo puzzles for Blindfold Square Vision.

Run:  python -m app.modules.blindfold_square_vision.seed
Idempotent: skips when puzzles for the slug already exist.
Every entry carries task parameters only (piece, color, from, to); the
correct distance is derived, never stored. Entries are independently
verified (valid data, reachable target, matching distribution) before
insert; invalid entries fail loudly instead of seeding a broken puzzle.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.blindfold_square_vision.validator import (
    SLUG,
    example_path,
    min_moves,
    normalize_color,
    normalize_piece,
    normalize_square,
)
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "این مهره با چند حرکت به خانه هدف می‌رسد؟"

# Each entry: piece, color, from, to, prompt, explanation, hints, rating.
# Ordered easy → hard within the required piece distribution.
PUZZLES: list[dict] = [
    {
        "piece": "K",
        "color": "white",
        "from": "e4",
        "to": "e5",
        "prompt_fa": PROMPT_FA,
        "explanation": "شاه در یک حرکت به هر خانه مجاور می‌رود؛ پس جواب ۱ است.",
        "hints": [{"id": "h1", "text_fa": "شاه در هر حرکت فقط یک خانه جلو می‌رود.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "piece": "K",
        "color": "white",
        "from": "a1",
        "to": "h8",
        "prompt_fa": PROMPT_FA,
        "explanation": "شاه هر بار یک خانه جلو می‌رود؛ از گوشه تا گوشه ۷ حرکت لازم است.",
        "hints": [{"id": "h1", "text_fa": "بزرگ‌ترین اختلاف سطر یا ستون را بشمار.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "piece": "K",
        "color": "black",
        "from": "c3",
        "to": "f6",
        "prompt_fa": PROMPT_FA,
        "explanation": "اختلاف ۳ ستون و ۳ ردیف؛ شاه مورب می‌رود و در ۳ حرکت می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "حرکت مورب شاه هم حساب می‌شود.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "piece": "Q",
        "color": "white",
        "from": "d4",
        "to": "d8",
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر در یک ستون است؛ پس در ۱ حرکت می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "سطر، ستون و قطرها را بررسی کن.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "piece": "Q",
        "color": "white",
        "from": "a1",
        "to": "h7",
        "prompt_fa": PROMPT_FA,
        "explanation": "نه سطر، نه ستون و نه قطر مشترک؛ وزیر در ۲ حرکت می‌رسد، مثلاً از h1.",
        "hints": [{"id": "h1", "text_fa": "اگر مستقیم نمی‌شود، وزیر همیشه در ۲ حرکت می‌رسد.", "rating_cost": 10}],
        "rating": 900.0,
    },
    {
        "piece": "R",
        "color": "white",
        "from": "a1",
        "to": "a8",
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ در یک ستون است؛ پس در ۱ حرکت می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "ببین آیا دو خانه در یک سطر یا ستون قرار دارند.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "piece": "R",
        "color": "black",
        "from": "a1",
        "to": "h8",
        "prompt_fa": PROMPT_FA,
        "explanation": "سطر و ستون فرق دارد؛ رخ اول به h1 و بعد به h8 می‌رود: ۲ حرکت.",
        "hints": [{"id": "h1", "text_fa": "رخ همیشه حداکثر در ۲ حرکت می‌رسد.", "rating_cost": 10}],
        "rating": 850.0,
    },
    {
        "piece": "B",
        "color": "white",
        "from": "c1",
        "to": "h6",
        "prompt_fa": PROMPT_FA,
        "explanation": "دو خانه روی یک قطرند؛ فیل در ۱ حرکت می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "اول بررسی کن که خانه شروع و هدف هم‌رنگ هستند یا نه.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "piece": "B",
        "color": "white",
        "from": "a1",
        "to": "d2",
        "prompt_fa": PROMPT_FA,
        "explanation": "هر دو خانه هم‌رنگ‌اند ولی روی یک قطر نیستند؛ فیل در ۲ حرکت می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "فیل روی خانه هم‌رنگ در حداکثر ۲ حرکت می‌رسد.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "piece": "N",
        "color": "white",
        "from": "a1",
        "to": "c2",
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب با یک حرکت L شکل از a1 به c2 می‌رسد؛ جواب ۱ است.",
        "hints": [{"id": "h1", "text_fa": "به خانه‌های L شکل فکر کن.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "piece": "N",
        "color": "white",
        "from": "a1",
        "to": "d4",
        "prompt_fa": PROMPT_FA,
        "explanation": "یک حرکت کافی نیست ولی با دو حرکت می‌شود؛ مثلاً a1 به b3 و بعد به d4.",
        "hints": [{"id": "h1", "text_fa": "اگر با یک حرکت نمی‌شود، دو حرکت را امتحان کن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "piece": "N",
        "color": "black",
        "from": "a1",
        "to": "e6",
        "prompt_fa": PROMPT_FA,
        "explanation": "مسیر a1 به b3 به d4 به e6 می‌رسد: ۳ حرکت.",
        "hints": [{"id": "h1", "text_fa": "خانه‌های میانی را یکی‌یکی جلو برو.", "rating_cost": 10}],
        "rating": 1150.0,
    },
    {
        "piece": "N",
        "color": "white",
        "from": "a1",
        "to": "h8",
        "prompt_fa": PROMPT_FA,
        "explanation": "گوشه تا گوشه برای اسب طولانی است؛ ۶ حرکت لازم است.",
        "hints": [{"id": "h1", "text_fa": "مسیرهای طولانی را قدم‌به‌قدم حساب کن.", "rating_cost": 15}],
        "rating": 1300.0,
    },
    {
        "piece": "P",
        "color": "white",
        "from": "e2",
        "to": "e5",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز سفید فقط جلو می‌رود؛ e2 به e4 و بعد e5 می‌رسد: ۲ حرکت.",
        "hints": [{"id": "h1", "text_fa": "جهت حرکت سرباز را در نظر بگیر.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "piece": "P",
        "color": "black",
        "from": "e7",
        "to": "e3",
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز سیاه به سمت پایین می‌رود؛ e7 به e5 و بعد e4 و e3 می‌رسد: ۳ حرکت.",
        "hints": [{"id": "h1", "text_fa": "سرباز سیاه به سمت رتبه‌های کوچک‌تر می‌رود.", "rating_cost": 10}],
        "rating": 1050.0,
    },
]


def verify_puzzle(item: dict) -> int:
    """Independently verify one puzzle definition; return its distance.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses raw square validation plus an
    independent recomputation, not the validator.
    """
    piece = normalize_piece(item.get("piece"))
    color = normalize_color(item.get("color"))
    origin = normalize_square(item.get("from"))
    dest = normalize_square(item.get("to"))
    if piece is None or color is None or origin is None or dest is None:
        raise ValueError(f"malformed puzzle data: {item}")
    # Independent recomputation: BFS over piece-specific geometry,
    # written separately from validator internals.
    from collections import deque

    knight_steps = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))

    def targets(square: str) -> list[str]:
        fx, fr = ord(square[0]) - ord("a"), int(square[1]) - 1
        out = []
        if piece == "K":
            out = [
                chr(ord("a") + fx + dx) + str(fr + dy + 1)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if (dx or dy) and 0 <= fx + dx < 8 and 0 <= fr + dy < 8
            ]
        elif piece == "Q":
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                f, r = fx + dx, fr + dy
                while 0 <= f < 8 and 0 <= r < 8:
                    out.append(chr(ord("a") + f) + str(r + 1))
                    f += dx
                    r += dy
        elif piece == "R":
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                f, r = fx + dx, fr + dy
                while 0 <= f < 8 and 0 <= r < 8:
                    out.append(chr(ord("a") + f) + str(r + 1))
                    f += dx
                    r += dy
        elif piece == "B":
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                f, r = fx + dx, fr + dy
                while 0 <= f < 8 and 0 <= r < 8:
                    out.append(chr(ord("a") + f) + str(r + 1))
                    f += dx
                    r += dy
        elif piece == "N":
            out = [
                chr(ord("a") + fx + dx) + str(fr + dy + 1)
                for dx, dy in knight_steps
                if 0 <= fx + dx < 8 and 0 <= fr + dy < 8
            ]
        else:  # piece == "P"
            step = 1 if color == "white" else -1
            start_rank = 1 if color == "white" else 6
            if 0 <= fr + step < 8:
                out.append(chr(ord("a") + fx) + str(fr + step + 1))
            if fr == start_rank and 0 <= fr + 2 * step < 8:
                out.append(chr(ord("a") + fx) + str(fr + 2 * step + 1))
        return out

    if origin == dest:
        distance: int | None = 0
    else:
        distance = None
        seen = {origin}
        queue: deque[tuple[str, int]] = deque([(origin, 0)])
        while queue:
            square, dist = queue.popleft()
            for nxt in targets(square):
                if nxt == dest:
                    distance = dist + 1
                    queue.clear()
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
    if distance is None:
        raise ValueError(f"unreachable puzzle data: {item}")
    if min_moves(piece, color, origin, dest) != distance:
        raise ValueError(f"distance mismatch: {item}")
    return distance


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="خانه‌یابی ذهنی",
            title_en="Blindfold Square Vision",
            description="کمترین حرکت لازم برای رسیدن به خانه هدف را حدس بزن.",
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
        answer = {
            "piece": item["piece"],
            "color": item["color"],
            "from": item["from"],
            "to": item["to"],
        }
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=None,
            position_json={
                "piece": item["piece"],
                "color": item["color"],
                "from": item["from"],
                "to": item["to"],
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
        print(f"seeded {n} blindfold-square-vision puzzles")
    finally:
        db.close()
