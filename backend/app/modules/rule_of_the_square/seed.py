"""Seed/demo puzzles for Rule of the Square.

Run:  python -m app.modules.rule_of_the_square.seed
Idempotent: skips when puzzles for the slug already exist.

FENs are GENERATED from structured seed data (never hand-typed), so the
stored positions always match their specification. Verification is fully
independent (raw python-chess, never the production validator): every
position must hold exactly one pawn plus both kings, kings must not touch,
nobody may be in check, pawns stay on ranks 2-7, and the rule outcome must
match the declared distribution (8 CAN_CATCH / 7 CANNOT_CATCH). Hints are
scanned for verdict words.

Security: answer_json (the FEN) is server-only. The visible board renders
from the ``Puzzle.fen`` column, which this exercise intentionally exposes;
position_json carries only the mode. The expected verdict is recomputed
from the stored FEN on every submission.
"""

import chess
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle
from app.modules.rule_of_the_square.description import describe_position
from app.modules.rule_of_the_square.validator import CAN_CATCH, SLUG, evaluate, square_squares

# Each entry: pawn square + color, defending king square, attacker's king
# square (far corner, never interferes), side to move, rating. The pair
# (e4/Kh3) appears twice with opposite turns: White to move the king is
# shut out, Black to move it steps into the square.
PUZZLES: list[dict] = [
    {"pawn": "e4", "white": True, "king": "e8", "own_king": "a1", "turn": "w", "rating": 750.0},
    {"pawn": "e4", "white": True, "king": "h3", "own_king": "a1", "turn": "w", "rating": 800.0},
    {"pawn": "a4", "white": True, "king": "b7", "own_king": "h1", "turn": "w", "rating": 850.0},
    {"pawn": "a4", "white": True, "king": "c3", "own_king": "h1", "turn": "w", "rating": 850.0},
    {"pawn": "e2", "white": True, "king": "e8", "own_king": "a1", "turn": "w", "rating": 900.0},
    {"pawn": "e2", "white": True, "king": "h2", "own_king": "a1", "turn": "w", "rating": 950.0},
    {"pawn": "g5", "white": True, "king": "e7", "own_king": "a1", "turn": "w", "rating": 900.0},
    {"pawn": "g5", "white": True, "king": "d4", "own_king": "a1", "turn": "w", "rating": 900.0},
    {"pawn": "e5", "white": False, "king": "e1", "own_king": "h8", "turn": "b", "rating": 800.0},
    {"pawn": "e5", "white": False, "king": "d7", "own_king": "h8", "turn": "w", "rating": 850.0},
    {"pawn": "e7", "white": False, "king": "a1", "own_king": "h8", "turn": "b", "rating": 950.0},
    {"pawn": "e7", "white": False, "king": "h8", "own_king": "e8", "turn": "b", "rating": 1000.0},
    {"pawn": "e4", "white": True, "king": "h3", "own_king": "a1", "turn": "b", "rating": 1000.0},
    {"pawn": "d4", "white": False, "king": "a6", "own_king": "h8", "turn": "w", "rating": 900.0},
    {"pawn": "d4", "white": False, "king": "e2", "own_king": "h8", "turn": "b", "rating": 950.0},
]

_HINT_NORMAL = [
    {"id": "h1", "text_fa": "به فاصله شاه از پیاده توجه کن.", "rating_cost": 5},
    {"id": "h2", "text_fa": "مربعی فرضی از موقعیت پیاده تا ردیف ارتقا در نظر بگیر.", "rating_cost": 10},
]

_HINT_START = [
    {"id": "h1", "text_fa": "به فاصله شاه از پیاده توجه کن.", "rating_cost": 5},
    {"id": "h2", "text_fa": "پیاده‌ای که هنوز حرکت نکرده می‌تواند دو خانه جلو برود؛ مربع را کوچک‌تر حساب کن.", "rating_cost": 10},
]

_VERDICT_WORDS = ("می‌رسد", "نمی‌رسد")


def build_fen(item: dict) -> str:
    """Generate the position FEN from structured seed data."""
    board = chess.Board.empty()
    pawn_color = chess.WHITE if item["white"] else chess.BLACK
    board.set_piece_at(chess.parse_square(item["pawn"]), chess.Piece(chess.PAWN, pawn_color))
    board.set_piece_at(chess.parse_square(item["king"]), chess.Piece(chess.KING, not pawn_color))
    board.set_piece_at(chess.parse_square(item["own_king"]), chess.Piece(chess.KING, pawn_color))
    board.turn = chess.WHITE if item["turn"] == "w" else chess.BLACK
    # Empty boards carry no castling rights and no en-passant square.
    return board.fen()


def explain(info: dict, item: dict) -> str:
    """Feedback generated from the puzzle's actual rule data."""
    pawn_color = "سفید" if info["pawn_is_white"] else "سیاه"
    king_color = "سیاه" if info["pawn_is_white"] else "سفید"
    start_rank = (info["pawn_is_white"] and item["pawn"][1] == "2") or (
        not info["pawn_is_white"] and item["pawn"][1] == "7"
    )
    if info["expected"] == CAN_CATCH:
        if not info["inside"]:
            return (
                f"شاه {king_color} در {info['king']} بیرون مربع است، ولی نوبت حرکت با اوست و "
                f"وارد مربع پیاده {pawn_color} در {info['pawn']} می‌شود؛ پس می‌رسد."
            )
        text = (
            f"شاه {king_color} در {info['king']} داخل مربع پیاده {pawn_color} در {info['pawn']} "
            "قرار دارد؛ پس قبل از ارتقا به پیاده می‌رسد."
        )
    else:
        text = (
            f"شاه {king_color} در {info['king']} بیرون از مربع پیاده {pawn_color} در {info['pawn']} "
            "قرار دارد؛ پس نمی‌تواند جلوی ارتقا را بگیرد."
        )
    if start_rank:
        text += " چون پیاده در خانه شروع است و می‌تواند دو خانه جلو برود، مربع کوچک‌تر حساب می‌شود."
    return text


def verify_puzzle(item: dict) -> tuple[str, dict]:
    """Independently verify one puzzle; return (fen, rule info)."""
    fen = build_fen(item)
    board = chess.Board(fen)
    pieces = [(sq, board.piece_at(sq)) for sq in chess.SQUARES if board.piece_at(sq)]
    if len(pieces) != 3:
        raise ValueError(f"expected K+k+pawn, got {len(pieces)}: {fen}")
    if sum(1 for _, p in pieces if p.piece_type == chess.PAWN) != 1:
        raise ValueError(f"expected exactly one pawn: {fen}")
    kings = [sq for sq, p in pieces if p.piece_type == chess.KING]
    if chess.square_distance(kings[0], kings[1]) < 2:
        raise ValueError(f"kings adjacent: {fen}")
    if board.is_check():
        raise ValueError(f"side to move in check: {fen}")
    pawn_rank = int(item["pawn"][1])
    if not 2 <= pawn_rank <= 7:
        raise ValueError(f"pawn offside: {fen}")
    info = evaluate(fen)
    # Teachability: on every seed the drawn square must visibly agree with
    # the verdict (inside, or stepping in with the defender to move), so
    # children are never shown a misleading picture.
    zone = square_squares(info["pawn"], info["pawn_is_white"])
    defender_turn = (board.turn == chess.BLACK) if info["pawn_is_white"] else (board.turn == chess.WHITE)
    stepping_in = defender_turn and any(
        chess.square_distance(chess.parse_square(info["king"]), chess.parse_square(sq)) == 1 for sq in zone
    )
    if (info["expected"] == CAN_CATCH) != bool(info["king"] in zone or stepping_in):
        raise ValueError(f"square disagrees with verdict: {fen}")
    describe_position(fen)
    return fen, info


def seed_db(db: Session) -> int:
    """Insert exercise + puzzles. Returns number of puzzles created."""
    verified = [verify_puzzle(item) for item in PUZZLES]
    if len({fen for fen, _ in verified}) != len(verified):
        raise ValueError("duplicate positions")
    outcomes = [info["expected"] for _, info in verified]
    if not (7 <= outcomes.count(CAN_CATCH) <= 8):
        raise ValueError(f"need a ~half split, got {outcomes}")

    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        exercise = Exercise(
            slug=SLUG,
            title_fa="قانون مربع",
            title_en="Rule of the Square",
            description="ببین شاه به پیاده می‌رسد یا نه.",
            is_active=True,
            sort_order=19,
        )
        db.add(exercise)
        db.commit()

    existing = db.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).count()
    if existing:
        return 0

    created = 0
    for item, (fen, info) in zip(PUZZLES, verified):
        start_rank = item["pawn"][1] in ("2", "7")
        hints = [dict(h) for h in (_HINT_START if start_rank else _HINT_NORMAL)]
        for hint in hints:
            for word in _VERDICT_WORDS:
                if word in hint["text_fa"]:
                    raise ValueError(f"hint leaks verdict: {hint}")
        puzzle = Puzzle(
            exercise_slug=SLUG,
            fen=fen,
            position_json={"mode": "square-rule"},
            answer_json={"fen": fen},
            hint_json={"hints": hints},
            prompt_fa="آیا شاه می‌تواند قبل از ارتقای پیاده، به آن برسد؟",
            explanation=explain(info, item),
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
        print(f"seeded {n} rule-of-the-square puzzles")
    finally:
        db.close()
