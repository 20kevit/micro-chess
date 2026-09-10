"""Seed/demo puzzles for Pin (Exercise 11, آچمز).

Run:  python -m app.modules.pin.seed
Idempotent: skips when current-shape puzzles for the slug already exist.

Each entry is a position that ALREADY contains exactly one classical pin.
The user identifies the three pieces in [pinner, pinned, behind] order;
no move is played. Every entry is verified before insert: the position
must contain exactly one pin under the validator's value-gated definition
(absolute = behind is the King; relative = behind strictly more valuable
than the pinned piece; skewers rejected), and the stored triplet must
match an independent re-scan. Invalid entries fail loudly instead of
seeding a broken puzzle.

Migration: legacy move-based rows (answer_json with "example" and no
"pin") are archived, never hard-deleted, before the new rows go in.
"""

from sqlalchemy.orm import Session

import chess

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.pin.validator import SLUG, find_pins
from app.modules.puzzles.models import Puzzle
from app.modules.puzzles.service import archive

PROMPT_FA = "سه مهره آچمز را به ترتیب انتخاب کن: اول مهره آچمزکننده، بعد مهره آچمزشده، بعد مهره پشتی."

# Each entry: fen, pin [pinner, pinned, behind], explanation (names the
# triplet in order), hints, rating.
PUZZLES: list[dict] = [
    {
        "fen": "4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1",
        "pin": ["e1", "e6", "e8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ e1 اسب e6 را به شاه e8 میخکوب کرده؛ چون پشت مهره شاه است، آچمز مطلق است.",
        "hints": [{"id": "h1", "text_fa": "رخ را پیدا کن که در یک ستون با دو مهره دشمن ایستاده.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "fen": "7k/6p1/8/8/8/8/1B6/4K3 w - - 0 1",
        "pin": ["b2", "g7", "h8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل b2 سرباز g7 را به شاه h8 میخکوب کرده؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "قطر فیل تا شاه حریف را دنبال کن.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "4k3/8/4b3/8/8/8/4Q3/4K3 w - - 0 1",
        "pin": ["e2", "e6", "e8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر e2 فیل e6 را به شاه e8 میخکوب کرده؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم در ستون و هم در قطر آچمز می‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "fen": "k3q3/8/4r3/8/8/8/8/4RK2 w - - 0 1",
        "pin": ["e1", "e6", "e8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ e1 رخ e6 را به وزیر e8 میخکوب کرده؛ چون پشت مهره وزیر است نه شاه، آچمز نسبی است.",
        "hints": [{"id": "h1", "text_fa": "پشت مهره هم می‌تواند وزیر باشد، نه فقط شاه.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "fen": "k7/8/8/2q5/1n6/B7/8/4K3 w - - 0 1",
        "pin": ["a3", "b4", "c5"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل a3 اسب b4 را به وزیر c5 میخکوب کرده؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "هر دو قطر فیل را بررسی کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "k7/4q3/8/4n3/8/8/4Q3/4K3 w - - 0 1",
        "pin": ["e2", "e5", "e7"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر e2 اسب e5 را به وزیر e7 میخکوب کرده؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "مهره ارزشمند پشتی هم جزو جواب است.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "2k5/8/8/8/2q5/8/8/2R1K3 w - - 0 1",
        "pin": ["c1", "c4", "c8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ c1 وزیر c4 را به شاه c8 میخکوب کرده؛ حتی وزیر هم می‌تواند آچمز شود.",
        "hints": [{"id": "h1", "text_fa": "هر مهره‌ای، حتی وزیر، می‌تواند آچمز شود.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "4k3/8/2p5/8/B7/8/8/4K3 w - - 0 1",
        "pin": ["a4", "c6", "e8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل a4 سرباز c6 را به شاه e8 میخکوب کرده؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "قطر بلند فیل را تا شاه دنبال کن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "8/7k/8/5n2/8/3B4/8/4K3 w - - 0 1",
        "pin": ["d3", "f5", "h7"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل d3 اسب f5 را به شاه h7 میخکوب کرده؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "مهره میانی و شاه پشتی در یک قطرند.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "fen": "7k/8/r7/8/b7/8/8/R3K3 w - - 0 1",
        "pin": ["a1", "a4", "a6"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ a1 فیل a4 را به رخ a6 میخکوب کرده؛ چون رخ از فیل ارزشمندتر است، آچمز نسبی است.",
        "hints": [{"id": "h1", "text_fa": "ارزش مهره پشتی را با مهره میانی مقایسه کن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "fen": "k6q/8/5r2/8/8/8/1B6/4K3 w - - 0 1",
        "pin": ["b2", "f6", "h8"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل b2 رخ f6 را به وزیر h8 میخکوب کرده؛ آچمز نسبی.",
        "hints": [{"id": "h1", "text_fa": "رخ هم می‌تواند قربانی آچمز شود.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "4k3/8/8/8/1b6/2N5/8/4K3 w - - 0 1",
        "pin": ["b4", "c3", "e1"],
        "prompt_fa": PROMPT_FA,
        "explanation": "فیل سیاه b4 اسب c3 را به شاه سفید e1 میخکوب کرده؛ آچمزکننده همیشه سفید نیست.",
        "hints": [{"id": "h1", "text_fa": "به رنگ مهره‌ها هم دقت کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "3r1k2/8/8/3B4/8/8/8/3K4 w - - 0 1",
        "pin": ["d8", "d5", "d1"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ سیاه d8 فیل d5 را به شاه سفید d1 میخکوب کرده؛ آچمز مطلق.",
        "hints": [{"id": "h1", "text_fa": "ستون d را از بالا تا پایین نگاه کن.", "rating_cost": 5}],
        "rating": 950.0,
    },
    {
        "fen": "8/4k3/8/2r5/8/Q7/8/4K3 w - - 0 1",
        "pin": ["a3", "c5", "e7"],
        "prompt_fa": PROMPT_FA,
        "explanation": "وزیر a3 رخ c5 را به شاه e7 میخکوب کرده؛ آچمز مطلق روی قطر.",
        "hints": [{"id": "h1", "text_fa": "قطر a3 تا e7 را دنبال کن.", "rating_cost": 10}],
        "rating": 1050.0,
    },
    {
        "fen": "k7/7r/8/8/7n/8/8/4K2R w - - 0 1",
        "pin": ["h1", "h4", "h7"],
        "prompt_fa": PROMPT_FA,
        "explanation": "رخ h1 اسب h4 را به رخ h7 میخکوب کرده؛ چون رخ از اسب ارزشمندتر است، آچمز نسبی است.",
        "hints": [{"id": "h1", "text_fa": "ستون h را از پایین تا بالا نگاه کن.", "rating_cost": 5}],
        "rating": 1000.0,
    },
]


def _independent_pins(fen: str) -> set[tuple[str, str, str]]:
    """Independent pin scan (slider's perspective, no shared code)."""
    board = chess.Board(fen)  # raises on invalid FEN
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    rays = {
        chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
        chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
        chess.QUEEN: [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)],
    }
    found = set()
    for slider_sq in chess.SQUARES:
        slider = board.piece_at(slider_sq)
        if slider is None or slider.piece_type not in rays:
            continue
        fx, rk = chess.square_file(slider_sq), chess.square_rank(slider_sq)
        for dx, dy in rays[slider.piece_type]:
            seen: list = []
            f, r = fx + dx, rk + dy
            while 0 <= f < 8 and 0 <= r < 8:
                occ = chess.square(f, r)
                if board.piece_at(occ) is not None:
                    seen.append(occ)
                    if len(seen) == 2:
                        break
                f += dx
                r += dy
            if len(seen) == 2:
                middle, behind = seen
                mid_piece = board.piece_at(middle)
                behind_piece = board.piece_at(behind)
                if mid_piece is None or behind_piece is None:
                    continue
                if mid_piece.piece_type == chess.KING:
                    continue
                if mid_piece.color == slider.color or behind_piece.color == slider.color:
                    continue
                if behind_piece.piece_type == chess.KING or values[behind_piece.piece_type] > values[
                    mid_piece.piece_type
                ]:
                    found.add((chess.square_name(slider_sq), chess.square_name(middle), chess.square_name(behind)))
    return found


def verify_puzzle(item: dict) -> None:
    """Independently verify one puzzle definition.

    Raises ValueError on any problem so seeding fails loudly instead of
    inserting a broken puzzle. The position must contain exactly one pin
    (no ambiguity, no skewer-only lines), and the stored triplet must
    equal it in [pinner, pinned, behind] order.
    """
    board = chess.Board(item["fen"])  # raises on invalid FEN
    if board.piece_at(chess.parse_square(item["pin"][0])) is None:
        raise ValueError(f"pinner square empty: {item['fen']} {item['pin']}")
    pins = find_pins(item["fen"])
    if len(pins) != 1:
        raise ValueError(f"need exactly one pin, found {len(pins)}: {item['fen']} {pins}")
    actual = [pins[0]["pinner"], pins[0]["pinned"], pins[0]["behind"]]
    if actual != list(item["pin"]):
        raise ValueError(f"stored pin {item['pin']} != detected {actual}: {item['fen']}")
    if _independent_pins(item["fen"]) != {(item["pin"][0], item["pin"][1], item["pin"][2])}:
        raise ValueError(f"independent scan disagrees: {item['fen']}")


def _is_legacy(row_answer: dict) -> bool:
    return isinstance(row_answer, dict) and "example" in row_answer and "pin" not in row_answer


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
            description="سه مهره آچمز را به ترتیب پیدا کن.",
            is_active=True,
            sort_order=10,
        )
        db.add(exercise)
        db.commit()

    # Archive legacy move-based rows (answer_json with "example"): the
    # contract changed from move-finding to triplet identification, so the
    # old rows are no longer answerable. Never hard-delete (history).
    legacy = (
        db.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False)  # noqa: E712
        .all()
    )
    for row in legacy:
        if _is_legacy(row.answer_json or {}):
            archive(db, row)

    existing = (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == SLUG,
            Puzzle.is_published == True,  # noqa: E712
            Puzzle.is_archived == False,  # noqa: E712
        )
        .count()
    )
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        answer = {"fen": item["fen"], "pin": list(item["pin"])}
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
