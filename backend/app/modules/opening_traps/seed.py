"""Seed/demo puzzles for Opening Traps Blindfold (one tactic per puzzle).

Run:  python -m app.modules.opening_traps.seed
Idempotent: skips when puzzles for the slug already exist.

Security: the FEN and the solution UCIs live ONLY in server-side
answer_json. The Puzzle.fen column stays NULL and position_json carries
just the Persian description, side to move, mode and opening context --
so the normal puzzle endpoint never leaks the position or any solution
before submission.

Every puzzle is independently verified (raw python-chess, never the
production validator): the FEN must parse, every solution UCI must be
legal and satisfy the puzzle's declared rule (capture / check / mate),
hints must not contain solution SANs, and FENs must be unique.
"""

import chess
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.opening_traps.description import THEME_FA, describe_trap, side_to_move
from app.modules.opening_traps.validator import SLUG
from app.modules.puzzles.models import Puzzle

# Each entry: genuine opening line behind it (see docs), FEN, UCI solutions,
# theme code, machine-checkable rule, Persian context, explanation (conceptual,
# no destination squares), hints (never the move), rating.
PUZZLES: list[dict] = [
    {
        "fen": "rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5",
        "solutions": ["f3e5"],
        "theme": "TRAP",
        "rule": "capture",
        "opening_fa": "دفاع فیلیدور",
        "trap_fa": "تله لگال",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "اسب سفید پیاده حریف را می‌گیرد؛ اگر وزیر سیاه اسب را بگیرد، قربانی فیل و مات با اسب دنبال می‌شود و اگر نگیرد، سفید وزیر می‌برد.",
        "hints": [
            {"id": "h1", "text_fa": "به مهره‌ای توجه کن که به نظر می‌رسد رایگان است ولی تله است.", "rating_cost": 5},
            {"id": "h2", "text_fa": "گرفتن یک پیاده وسط صفحه می‌تواند وزیر حریف را زیر ضربه ببرد.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "fen": "r1b1kbnr/pppp1ppp/8/4N1q1/2BnP3/8/PPPP1PPP/RNBQK2R w KQkq - 1 5",
        "solutions": ["c4f7"],
        "theme": "TRAP",
        "rule": "check",
        "opening_fa": "بازی ایتالیایی",
        "trap_fa": "گامبی شیلینگ بلک‌برن",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "فیل با کیش قربانی می‌شود؛ شاه سیاه مجبور به حرکت است و وزیرش در ادامه شکار می‌شود.",
        "hints": [
            {"id": "h1", "text_fa": "به شاه حریف که هنوز قلعه نرفته توجه کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "یک کیش با فیل می‌تواند شاه را بیرون بکشد.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
    {
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "solutions": ["h5f7"],
        "theme": "MATE_THREAT",
        "rule": "mate",
        "opening_fa": "بازی ایتالیایی",
        "trap_fa": "مات دانش‌آموزی",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "وزیر پیاده جلوی شاه را می‌زند و مات می‌کند؛ اسب حریف نمی‌تواند جلوی هر دو ضربه را بگیرد.",
        "hints": [
            {"id": "h1", "text_fa": "به خانه‌های اطراف شاه حریف نگاه کن؛ کدام پیاده بی‌دفاع است؟", "rating_cost": 5},
            {"id": "h2", "text_fa": "وزیر می‌تواند با حمایت فیل، ضربه نهایی را بزند.", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
        "solutions": ["d8h4"],
        "theme": "MATE_THREAT",
        "rule": "mate",
        "opening_fa": "شروع فرعی",
        "trap_fa": "مات احمق",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی سیاه را پیدا کن.",
        "explanation": "سفید با حرکت‌های پیاده‌ای شاه خودش را بی‌دفاع کرده است؛ وزیر سیاه با یک کیش دور مات می‌کند.",
        "hints": [
            {"id": "h1", "text_fa": "به نوبت حرکت دقت کن: این بار سیاه ضربه می‌زند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "کدام قطر به شاه سفید باز مانده است؟", "rating_cost": 10},
        ],
        "rating": 800.0,
    },
    {
        "fen": "r1bqkb1r/1p3ppp/2np1n2/1p1Np1B1/4P3/8/PPP2PPP/R2QKB1R w KQkq - 0 9",
        "solutions": ["g5f6"],
        "theme": "WIN_EXCHANGE",
        "rule": "capture",
        "opening_fa": "دفاع سیسیلی",
        "trap_fa": "تله سیبری",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "فیل اسب مدافع را می‌گیرد؛ بعد از پس‌گرفتن، اسب سفید با کیش رخ را شکار می‌کند و سفید تعویض می‌برد.",
        "hints": [
            {"id": "h1", "text_fa": "به اسبی توجه کن که از وزیر حریف دفاع می‌کند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "حذف مدافع می‌تواند راه چنگال اسب را باز کند.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
    {
        "fen": "r1bqkbnr/5ppp/p2p4/1pp5/3QP3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 9",
        "solutions": ["d4c5", "d4g7"],
        "theme": "MATERIAL_WIN",
        "rule": "capture",
        "opening_fa": "روئی لوپز",
        "trap_fa": "تله کشتی نوح",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "وزیر سفید دو پیاده بی‌دفاع حریف را زیر ضربه دارد؛ هر کدام را بزند مهره می‌برد.",
        "hints": [
            {"id": "h1", "text_fa": "وزیر سفید در مرکز فعال است؛ پیاده‌های بی‌دفاع حریف را بشمار.", "rating_cost": 5},
            {"id": "h2", "text_fa": "بیشتر از یک پیاده را می‌شود زد؛ هر کدام برد است.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "r1bqkb1r/pp2nppp/2pp1n2/1B6/2N1P3/3P4/PPP2PPP/RNBQK2R w KQkq - 0 7",
        "solutions": ["c4d6"],
        "theme": "FORK",
        "rule": "check",
        "opening_fa": "روئی لوپز",
        "trap_fa": "تله مورتیمر",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "اسب با کیش جلو می‌آید و بعد شاه و رخ را همزمان زیر ضربه می‌برد؛ سیاه مهره سنگین از دست می‌دهد.",
        "hints": [
            {"id": "h1", "text_fa": "به شاه حریف که هنوز قلعه نرفته توجه کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب می‌تواند با کیش بیاید و بعد چنگال بزند.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
    {
        "fen": "rnbqkb1r/ppp2ppp/5n2/3P4/4p3/5N2/PPPPQPPP/RNB1KB1R w KQkq - 2 5",
        "solutions": ["e2e4"],
        "theme": "MATERIAL_WIN",
        "rule": "check",
        "opening_fa": "گامبی فیل",
        "trap_fa": "تله گامبی فیل",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "وزیر پیاده پیشروی حریف را با کیش پس می‌گیرد؛ سفید یک پیاده جلو می‌افتد.",
        "hints": [
            {"id": "h1", "text_fa": "پیاده‌ای که زیادی جلو آمده است را پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "وزیر می‌تواند با کیش آن پیاده را بگیرد.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "fen": "rnbqkbnr/pppp2pp/5p2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3",
        "solutions": ["f3e5"],
        "theme": "TRAP",
        "rule": "capture",
        "opening_fa": "بازی باز",
        "trap_fa": "دفاع دامیانو",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "اسب پیاده مرکزی را می‌گیرد؛ اگر سیاه پس بگیرد، وزیر سفید با کیش وارد می‌شود و حمله تعیین‌کننده است.",
        "hints": [
            {"id": "h1", "text_fa": "پیاده‌ای که دفاعش سست است را پیدا کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب با گرفتن آن پیاده، راه وزیر را باز می‌کند.", "rating_cost": 10},
        ],
        "rating": 850.0,
    },
    {
        "fen": "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        "solutions": ["g5f7"],
        "theme": "TRAP",
        "rule": "capture",
        "opening_fa": "بازی ایتالیایی",
        "trap_fa": "حمله جگر",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "اسب قربانی می‌شود و شاه سیاه را بیرون می‌کشد؛ حمله بعدی سفید تعیین‌کننده است.",
        "hints": [
            {"id": "h1", "text_fa": "به شاه حریف که هنوز قلعه نرفته توجه کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "قربانی اسب می‌تواند شاه را به وسط صفحه بکشاند.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "r1bqk2r/ppp2ppp/2p2n2/2b3B1/4P3/3P4/PPP2PPP/RN1QKB1R b KQkq - 2 6",
        "solutions": ["f6e4"],
        "theme": "TRAP",
        "rule": "capture",
        "opening_fa": "گامبی استافورد",
        "trap_fa": "تله استافورد",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی سیاه را پیدا کن.",
        "explanation": "اسب سیاه مهره مرکزی را می‌گیرد؛ اگر سفید طمع کند و وزیر را بگیرد، قربانی فیل و مات دنبال می‌شود.",
        "hints": [
            {"id": "h1", "text_fa": "به نوبت حرکت دقت کن: این بار سیاه ضربه می‌زند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل سفید بی‌دفاع است؛ اسب می‌تواند مرکز را بگیرد.", "rating_cost": 10},
        ],
        "rating": 1000.0,
    },
    {
        "fen": "r1bBkb1r/pppn1ppp/8/3n4/3P4/8/PP2PPPP/R2QKBNR b KQkq - 0 7",
        "solutions": ["f8b4"],
        "theme": "WIN_QUEEN",
        "rule": "check",
        "opening_fa": "گامبی وزیر ردشده",
        "trap_fa": "تله روبینشتاین",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی سیاه را پیدا کن.",
        "explanation": "سفید طمع کرده و وزیر سیاه را گرفته است؛ فیل با کیش برمی‌گردد و وزیر سفید شکار می‌شود.",
        "hints": [
            {"id": "h1", "text_fa": "به نوبت حرکت دقت کن: این بار سیاه ضربه می‌زند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "فیل می‌تواند با کیش وزیر حریف را زیر ضربه ببرد.", "rating_cost": 10},
        ],
        "rating": 1050.0,
    },
    {
        "fen": "r1b1k2r/ppppqppp/2n5/4P3/1bP2Bn1/P4N2/1P1NPPPP/R2QKB1R b KQkq - 0 7",
        "solutions": ["c6e5"],
        "theme": "MATERIAL_WIN",
        "rule": "capture",
        "opening_fa": "گامبی بوداپست",
        "trap_fa": "تله کینینگر",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی سیاه را پیدا کن.",
        "explanation": "اسب سیاه پیاده پیشروی سفید را می‌گیرد؛ سفید نمی‌تواند بدون از دست دادن مهره بیشتر آن را پس بگیرد.",
        "hints": [
            {"id": "h1", "text_fa": "به نوبت حرکت دقت کن: این بار سیاه ضربه می‌زند.", "rating_cost": 5},
            {"id": "h2", "text_fa": "پیاده‌ای که زیادی جلو آمده است را پیدا کن.", "rating_cost": 10},
        ],
        "rating": 950.0,
    },
    {
        "fen": "r2qk1nr/pppb1ppp/2np4/b7/2BpP3/1QP2N2/P4PPP/RNB2RK1 w kq - 2 9",
        "solutions": ["b3b7", "c4f7"],
        "theme": "TRAP",
        "rule": "capture",
        "opening_fa": "گامبی اوانز",
        "trap_fa": "تله گامبی اوانز",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "وزیر و فیل سفید دو نقطه ضعف را همزمان زیر ضربه دارند؛ زدن هر کدام برتری می‌دهد.",
        "hints": [
            {"id": "h1", "text_fa": "سفید دو تهدید همزمان دارد؛ هر دو را بررسی کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "بیشتر از یک زدن خوب وجود دارد؛ هر کدام برد است.", "rating_cost": 10},
        ],
        "rating": 1050.0,
    },
    {
        "fen": "r1bqkb1r/pp1npppp/2p2n2/8/3PN3/8/PPP1QPPP/R1B1KBNR w KQkq - 3 6",
        "solutions": ["e4d6"],
        "theme": "MATE_THREAT",
        "rule": "mate",
        "opening_fa": "دفاع کاروکان",
        "trap_fa": "مات کاروکان",
        "prompt_fa": "بدون دیدن صفحه، حرکت تاکتیکی درست را پیدا کن.",
        "explanation": "اسب با کیش وارد می‌شود و شاه سیاه که بین مهره‌های خودش گیر کرده است هیچ راه فراری ندارد.",
        "hints": [
            {"id": "h1", "text_fa": "به شاه حریف که بین مهره‌های خودش گیر کرده توجه کن.", "rating_cost": 5},
            {"id": "h2", "text_fa": "اسب می‌تواند با کیش مات کند.", "rating_cost": 10},
        ],
        "rating": 900.0,
    },
]


def verify_puzzle(item: dict) -> list[str]:
    """Independently verify one puzzle (raw python-chess only).

    Returns the canonical solution SANs. Fails loudly on any problem:
    bad FEN, unknown theme/rule, illegal solution, solution missing the
    declared tactical property, hint leaking a solution, bad side info.
    """
    if item["theme"] not in THEME_FA:
        raise ValueError(f"unknown theme: {item['theme']}")
    if item["rule"] not in ("capture", "check", "mate"):
        raise ValueError(f"unknown rule: {item['rule']}")

    board = chess.Board(item["fen"])  # raises on invalid FEN
    sans: list[str] = []
    for uci in item["solutions"]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            raise ValueError(f"bad UCI {uci!r} in {item['fen']}")
        if move not in board.legal_moves:
            raise ValueError(f"illegal solution {uci} in {item['fen']}")
        san = board.san(move)
        if item["rule"] == "capture" and not board.is_capture(move):
            raise ValueError(f"solution {uci} is no capture in {item['fen']}")
        board.push(move)
        try:
            is_check = board.is_check()
            is_mate = board.is_checkmate()
        finally:
            board.pop()
        if item["rule"] == "check" and not is_check:
            raise ValueError(f"solution {uci} gives no check in {item['fen']}")
        if item["rule"] == "mate" and not is_mate:
            raise ValueError(f"solution {uci} is no mate in {item['fen']}")
        sans.append(san)

    for hint in item["hints"]:
        for san in sans:
            if san in hint["text_fa"]:
                raise ValueError(f"hint leaks solution {san} in {item['fen']}")
    # Description must generate without errors (blindfold suitability).
    describe_trap(item["fen"], item["opening_fa"], item["trap_fa"])
    return sorted(sans)


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    for item in PUZZLES:
        verify_puzzle(item)
    fens = [item["fen"] for item in PUZZLES]
    if len(set(fens)) != len(fens):
        raise ValueError("duplicate puzzle positions")
    if sum(1 for item in PUZZLES if len(item["solutions"]) > 1) < 2:
        raise ValueError("need at least two multi-solution puzzles")

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="تله‌های گشایشی",
            title_en="Opening Traps",
            description="تاکتیک تله‌های گشایشی را ذهنی پیدا کن.",
            is_active=True,
            sort_order=17,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item in PUZZLES:
        sans = verify_puzzle(item)
        answer = {"fen": item["fen"], "solutions": sorted(item["solutions"]), "theme": item["theme"]}
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=None,
            position_json={
                "description_fa": describe_trap(item["fen"], item["opening_fa"], item["trap_fa"]),
                "side_to_move": side_to_move(item["fen"]),
                "mode": "tactic-1",
                "opening_fa": item["opening_fa"],
                "trap_fa": item["trap_fa"],
                "theme": item["theme"],
                "theme_fa": THEME_FA[item["theme"]],
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
        print(f"seeded {n} opening-traps puzzles")
    finally:
        db.close()
