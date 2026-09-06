"""Seed/demo puzzles for Pin.

Run:  python -m app.modules.pin.seed
Idempotent: skips when puzzles for the slug already exist.
Each entry carries an example move that creates a pin, independently
verified with raw python-chess (move legal, new pin present afterwards)
before insert; invalid entries fail loudly instead of seeding a broken
puzzle. Validation itself never depends on the example: any legal move
that creates a new pin is accepted.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.pin.validator import SLUG, find_pins
from app.modules.puzzles.models import Puzzle

PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}

PROMPT_FA = "با یک حرکت قانونی، یک آچمز کلاسیک بساز."

# Each entry: fen, example from/to (+promotion), explanation (which piece is
# pinned, what is behind it, which slider pins it, absolute or relative),
# hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1",
        "example": {"from": "a1", "to": "e1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ به e1 می‌رود و اسب e6 را به شاه e8 میخکوب می‌کند؛ چون پشت مهره شاه است، آچمز مطلق است.",
        "hints": [{"id": "h1", "text_fa": "رخ را به ستونی ببر که مهره دشمن و شاه پشت آن باشند.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "7k/6p1/8/8/8/8/8/2B1K3 w - - 0 1",
        "example": {"from": "c1", "to": "b2"},
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل به b2 می‌رود و سرباز g7 را به شاه h8 میخکوب می‌کند؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "قطر فیل تا شاه حریف را پیدا کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/4b3/8/8/8/8/3QK3 w - - 0 1",
        "example": {"from": "d1", "to": "e2"},
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر به e2 می‌رود و فیل e6 را به شاه e8 میخکوب می‌کند؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم در ستون و هم در قطر آچمز می‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "k3q3/8/4r3/8/8/8/8/R4K2 w - - 0 1",
        "example": {"from": "a1", "to": "e1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ به e1 می‌رود و رخ e6 را به وزیر e8 میخکوب می‌کند؛ چون پشت مهره وزیر است نه شاه، آچمز نسبی است.",
        "hints": [{"id": "h1", "text_fa": "پشت مهره هم می‌تواند وزیر باشد، نه فقط شاه.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "k7/8/8/2q5/1n6/8/8/2B1K3 w - - 0 1",
        "example": {"from": "c1", "to": "a3"},
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل به a3 می‌رود و اسب b4 را به وزیر c5 میخکوب می‌کند؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "دو قطر فیل را بررسی کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "k7/4q3/8/4n3/8/8/8/3QK3 w - - 0 1",
        "example": {"from": "d1", "to": "e2"},
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر به e2 می‌رود و اسب e5 را به وزیر e7 میخکوب می‌کند؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "مهره ارزشمند پشت هم جزو جواب است.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "2k5/8/8/8/2q5/8/8/R3K3 w - - 0 1",
        "example": {"from": "a1", "to": "c1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ به c1 می‌رود و وزیر c4 را به شاه c8 میخکوب می‌کند؛ حتی وزیر هم می‌تواند آچمز شود.",
        "hints": [{"id": "h1", "text_fa": "هر مهره‌ای، حتی وزیر، می‌تواند آچمز شود.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "8/8/7k/8/5n2/8/3P4/2B1K3 w - - 0 1",
        "example": {"from": "d2", "to": "d4"},
        "prompt_fa": PROMPT_FA,
        "explanation": "سرباز از قطر فیل کنار می‌رود و فیل c1 اسب f4 را به شاه h6 میخکوب می‌کند؛ آچمز را سرباز با حرکت خودش ساخت.",
        "hints": [{"id": "h1", "text_fa": "گاهی کنار رفتن یک سرباز، خط حمله را باز می‌کند.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "7k/8/5n2/8/3N4/8/1B6/4K3 w - - 0 1",
        "example": {"from": "d4", "to": "e6"},
        "prompt_fa": PROMPT_FA,
        "explanation": "اسب از قطر فیل کنار می‌رود و فیل b2 اسب f6 را به شاه h8 میخکوب می‌کند.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که راه را بسته، خودش حرکت کند.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "k7/8/8/8/6q1/5n2/4K3/3Q4 w - - 0 1",
        "example": {"from": "e2", "to": "f1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "شاه از قطر وزیر کنار می‌رود و وزیر d1 اسب f3 را به وزیر g4 میخکوب می‌کند؛ حتی حرکت شاه هم می‌تواند آچمز بسازد.",
        "hints": [{"id": "h1", "text_fa": "شاه هم می‌تواند با حرکتش خط را باز کند.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "k7/4q3/8/4n3/n7/8/3Q4/1R4K1 w - - 0 1",
        "example": {"from": "b1", "to": "a1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "هم رخ با a1 اسب a4 را به شاه a8 میخکوب می‌کند، هم وزیر با e2 اسب e5 را به وزیر e7؛ هر دو حرکت درست است.",
        "hints": [{"id": "h1", "text_fa": "گاهی بیش از یک آچمز ممکن است؛ یکی کافی است.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "7k/4q3/4nn2/8/8/8/1B6/R5K1 w - - 0 1",
        "example": {"from": "a1", "to": "e1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل b2 از قبل اسب f6 را به شاه h8 میخکوب کرده؛ رخ با e1 یک آچمز تازه روی اسب e6 به وزیر e7 می‌سازد. آچمز قبلی به‌تنهایی کافی نیست.",
        "hints": [{"id": "h1", "text_fa": "آچمزی که از قبل هست حساب نیست؛ یکی تازه بساز.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "fen": "4k3/8/4n3/8/3Q4/8/8/R5K1 w - - 0 1",
        "example": {"from": "a1", "to": "e1"},
        "prompt_fa": PROMPT_FA,
        "explanation": "گرفتن اسب با وزیر وسوسه‌انگیز است ولی آچمزی نمی‌سازد؛ رخ با e1 اسب را به شاه میخکوب می‌کند.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره همیشه آچمز نیست.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "3qk3/8/8/8/8/8/3P4/4K3 b - - 0 1",
        "example": {"from": "d8", "to": "a5"},
        "prompt_fa": PROMPT_FA,
        "explanation": "نوبت با سیاه است؛ وزیر به a5 می‌رود و سرباز d2 را به شاه e1 میخکوب می‌کند.",
        "hints": [{"id": "h1", "text_fa": "به نوبت حرکت دقت کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "k6q/8/5r2/8/8/8/8/2B1K3 w - - 0 1",
        "example": {"from": "c1", "to": "b2"},
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل به b2 می‌رود و رخ f6 را به وزیر h8 میخکوب می‌کند؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "رخ هم می‌تواند قربانی آچمز شود.", "rating_cost": 5}],
        "rating": 900.0,
    },
]


def _pin_key(pin: dict) -> tuple[str, str, str]:
    return (pin["pinned"], pin["behind"], pin["pinner"])


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition with raw python-chess.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. Uses direct move generation plus an
    independent pin scan, not the validator.
    """
    board = chess.Board(item["fen"])  # raises on invalid FEN
    example = item["example"]
    move = chess.Move(
        chess.parse_square(example["from"]),
        chess.parse_square(example["to"]),
        promotion=PROMOTIONS.get(example.get("promotion")) if example.get("promotion") else None,
    )
    if move not in board.legal_moves:
        raise ValueError(f"example move not legal: {item['fen']} {example}")

    def scan(fen: str) -> set[tuple[str, str, str]]:
        # Independent pin scan: walk each enemy slider's rays directly.
        b = chess.Board(fen)
        found = set()
        rays = {
            chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
            chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
            chess.QUEEN: [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)],
        }
        for sq in chess.SQUARES:
            piece = b.piece_at(sq)
            if piece is None or piece.piece_type not in rays:
                continue
            fx, rk = chess.square_file(sq), chess.square_rank(sq)
            for dx, dy in rays[piece.piece_type]:
                seen: list = []
                f, r = fx + dx, rk + dy
                while 0 <= f < 8 and 0 <= r < 8:
                    occ = chess.square(f, r)
                    if b.piece_at(occ) is not None:
                        seen.append(occ)
                        if len(seen) == 2:
                            break
                    f += dx
                    r += dy
                if len(seen) == 2:
                    middle, behind = seen
                    mid_piece = b.piece_at(middle)
                    behind_piece = b.piece_at(behind)
                    if (
                        mid_piece is not None
                        and behind_piece is not None
                        and mid_piece.color != piece.color
                        and behind_piece.color != piece.color
                    ):
                        found.add(
                            (chess.square_name(middle), chess.square_name(behind), chess.square_name(sq))
                        )
        return found

    before = scan(item["fen"])
    board.push(move)
    try:
        after = scan(board.fen())
    finally:
        board.pop()
    if not (after - before):
        raise ValueError(f"example move creates no pin: {item['fen']} {example}")


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="آچمز",
            title_en="Pin",
            description="با یک حرکت قانونی، یک آچمز کلاسیک بساز.",
            is_active=True,
            sort_order=7,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"], "example": item["example"]}
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
        print(f"seeded {n} pin puzzles")
    finally:
        db.close()
