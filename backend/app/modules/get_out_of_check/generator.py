"""Get Out of Check puzzle generator: synthetic in-check positions.

Unlike Exercises 1-5 this exercise cannot sample the shared ``puzzles.db``
(the exercise needs positions where the side to move is IN check, which
the Giving Check generator explicitly rejects). Positions are therefore
constructed parametrically, family by family, and every candidate is
verified with the authoritative ``escaping_moves`` solver before it is
accepted:

1. place the White king (+ a distant Black king, never adjacent),
2. place checker(s) according to the drawn family,
3. sprinkle White helpers (captures/blocks/decoys) and Black extras,
4. verify: White in check, NOT checkmate, >= 1 escape, sane size,
5. reject checkmates and zero-answer positions outright.

The persisted row plugs into the standard attempt flow unchanged
(``POST /api/v1/attempts`` derives the answer from the stored FEN).
Identical FEN rows are reused, not duplicated; ``exclude_ids`` steers
away from just-shown puzzles (bounded re-roll; best-effort).

Family mixture (weights sum to 100):
- rook 22 / queen 22 / bishop 16 (line checks; blockable unless adjacent)
- knight 16 (never blockable) / pawn 10 (never blockable)
- double 14 (genuine double check: only king moves escape)
"""

from __future__ import annotations

import random

import chess
from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.get_out_of_check.validator import SLUG, escaping_moves
from app.modules.puzzles.models import Puzzle

PROMPT_FA = "تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند."

HINT_FA = (
    "شاه را می‌شود حرکت داد، مهره کیش‌دهنده را زد، یا جلوی کیش خطی مهره گذاشت؛ "
    "در کیش دوبل فقط شاه می‌تواند حرکت کند."
)

TITLE_FA = "رفع کیش"

# This exercise's position in the roadmap (right after Giving Check).
SORT_ORDER = 5

MAX_ATTEMPTS = 200
# Quality window for the answer count: every puzzle needs >= 1 escape
# (0 means checkmate, rejected above); the upper cap keeps "find them
# all" teachable instead of overwhelming.
MAX_ESCAPES = 12

_FAMILIES = ("rook", "queen", "bishop", "knight", "pawn", "double")
_FAMILY_WEIGHTS = (22, 22, 16, 16, 10, 14)

# White-king homes: mostly back-rank/edge squares (realistic checks) with
# a few central squares for variety.
_KING_SQUARES = (
    "e1", "d1", "f1", "c1", "g1", "h1", "a1",
    "e2", "d2", "f2", "g2",
    "e3", "d4", "f3",
)

_WHITE_HELPERS = (
    chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN,
)
_BLACK_EXTRAS = (
    chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN,
)


def _squares() -> list[int]:
    return list(chess.SQUARES)


def _random_empty(board: chess.Board, rng: random.Random) -> int | None:
    empties = [sq for sq in _squares() if board.piece_at(sq) is None]
    if not empties:
        return None
    return rng.choice(empties)


def _chebyshev(a: int, b: int) -> int:
    return max(abs(chess.square_file(a) - chess.square_file(b)), abs(chess.square_rank(a) - chess.square_rank(b)))


def _place_black_king(board: chess.Board, white_king: int, rng: random.Random) -> bool:
    """Park the Black king far from the White king (never adjacent)."""
    far = [sq for sq in _squares() if board.piece_at(sq) is None and _chebyshev(sq, white_king) >= 4]
    if not far:
        return False
    board.set_piece_at(rng.choice(far), chess.Piece(chess.KING, chess.BLACK))
    return True


def _line_squares(king: int, direction: tuple[int, int]) -> list[int]:
    """Squares along one ray from the king (nearest first)."""
    out: list[int] = []
    f, r = chess.square_file(king), chess.square_rank(king)
    df, dr = direction
    f, r = f + df, r + dr
    while 0 <= f < 8 and 0 <= r < 8:
        out.append(chess.square(f, r))
        f, r = f + df, r + dr
    return out


def _place_slider(
    board: chess.Board, king: int, piece_type: chess.PieceType, rng: random.Random
) -> bool:
    """Place a rook/bishop/queen giving check along a random line.

    Distance 1 (adjacent) is sometimes kept: such checks cannot be
    blocked, which teaches the non-blockable case for sliders too.
    """
    if piece_type == chess.ROOK:
        rays = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    elif piece_type == chess.BISHOP:
        rays = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    else:
        rays = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    rng.shuffle(rays)
    for ray in rays:
        line = _line_squares(king, ray)
        if not line:
            continue
        # Adjacent check ~25% of the time (when the ray allows it).
        distance = 1 if rng.random() < 0.25 else rng.randint(1, len(line))
        target = line[distance - 1]
        if board.piece_at(target) is not None:
            continue
        board.set_piece_at(target, chess.Piece(piece_type, chess.BLACK))
        return True
    return False


def _place_knight_check(board: chess.Board, king: int, rng: random.Random) -> bool:
    kf, kr = chess.square_file(king), chess.square_rank(king)
    spots = []
    for df, dr in ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)):
        f, r = kf + df, kr + dr
        if 0 <= f < 8 and 0 <= r < 8:
            sq = chess.square(f, r)
            if board.piece_at(sq) is None:
                spots.append(sq)
    if not spots:
        return False
    board.set_piece_at(rng.choice(spots), chess.Piece(chess.KNIGHT, chess.BLACK))
    return True


def _place_pawn_check(board: chess.Board, king: int, rng: random.Random) -> bool:
    """Place a Black pawn attacking the White king (never blockable)."""
    kf, kr = chess.square_file(king), chess.square_rank(king)
    spots = []
    for df in (-1, 1):
        f, r = kf + df, kr + 1
        if 0 <= f < 8 and 0 <= r < 8:
            sq = chess.square(f, r)
            # Pawns may never stand on the last rank.
            if r <= 6 and board.piece_at(sq) is None:
                spots.append(sq)
    if not spots:
        return False
    board.set_piece_at(rng.choice(spots), chess.Piece(chess.PAWN, chess.BLACK))
    return True


def _place_checkers(board: chess.Board, king: int, family: str, rng: random.Random) -> bool:
    if family == "rook":
        return _place_slider(board, king, chess.ROOK, rng)
    if family == "bishop":
        return _place_slider(board, king, chess.BISHOP, rng)
    if family == "queen":
        return _place_slider(board, king, chess.QUEEN, rng)
    if family == "knight":
        return _place_knight_check(board, king, rng)
    if family == "pawn":
        return _place_pawn_check(board, king, rng)
    # Double check: a knight plus a slider, both attacking the king.
    if not _place_knight_check(board, king, rng):
        return False
    slider = rng.choice([chess.ROOK, chess.BISHOP, chess.QUEEN])
    return _place_slider(board, king, slider, rng)
    # NOTE: the knight square may block the slider ray; the final
    # ``checkers == 2`` gate below rejects such candidates.


def _sprinkle_helpers(board: chess.Board, rng: random.Random) -> None:
    """Add White helpers (capture/block resources and decoys)."""
    for _ in range(rng.randint(1, 3)):
        sq = _random_empty(board, rng)
        if sq is None:
            return
        rank = chess.square_rank(sq)
        kind = rng.choice(_WHITE_HELPERS)
        if kind == chess.PAWN and rank in (0, 7):
            continue
        board.set_piece_at(sq, chess.Piece(kind, chess.WHITE))


def _sprinkle_black_extras(board: chess.Board, white_king: int, rng: random.Random) -> None:
    """Add 0-2 Black extras (escape-square guards and decoys)."""
    for _ in range(rng.randint(0, 2)):
        sq = _random_empty(board, rng)
        if sq is None:
            return
        if _chebyshev(sq, white_king) <= 1:
            continue  # keep the king's neighborhood readable
        rank = chess.square_rank(sq)
        kind = rng.choice(_BLACK_EXTRAS)
        if kind == chess.PAWN and rank in (0, 7):
            continue
        board.set_piece_at(sq, chess.Piece(kind, chess.BLACK))


def generate_candidate(rng: random.Random) -> tuple[str, str] | None:
    """Build one candidate position. Returns (fen, family) or None."""
    family = rng.choices(_FAMILIES, weights=_FAMILY_WEIGHTS, k=1)[0]
    board = chess.Board.empty()
    board.turn = chess.WHITE

    king = chess.parse_square(rng.choice(_KING_SQUARES))
    board.set_piece_at(king, chess.Piece(chess.KING, chess.WHITE))
    if not _place_black_king(board, king, rng):
        return None
    if not _place_checkers(board, king, family, rng):
        return None
    _sprinkle_helpers(board, rng)
    _sprinkle_black_extras(board, king, rng)

    if not board.is_valid():
        return None
    if not board.is_check():
        return None
    if board.is_checkmate():
        return None
    checkers = board.checkers()
    if family == "double":
        if len(checkers) < 2:
            return None
    elif len(checkers) != 1:
        return None
    try:
        escapes = escaping_moves(board.fen())
    except ValueError:
        return None
    if not escapes or len(escapes) > MAX_ESCAPES:
        return None
    if family == "double":
        # Genuine double check: only king moves may escape.
        king_sq = chess.square_name(king)
        if any(uci[:2] != king_sq for uci in escapes):
            return None
    return board.fen(), family


def generate_question_data(rng: random.Random | None = None) -> dict:
    """Generate one verified question/answer bundle (no DB)."""
    rng = rng if rng is not None else random
    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            candidate = generate_candidate(rng)
        except Exception as exc:  # never crash the request path
            last_error = exc
            continue
        if candidate is None:
            continue
        fen, family = candidate
        return question_for_fen(fen, family)
    raise RuntimeError(f"could not generate a get-out-of-check puzzle: {last_error}")


def explanation_for(moves: list[str], family: str | None) -> str:
    base = f"{len(moves)} حرکت شاه را از کیش خارج می‌کند."
    if family == "double":
        return base + " کیش دوبل است؛ فقط حرکت شاه نجات می‌دهد."
    return base


def question_for_fen(fen: str, family: str | None = None) -> dict:
    """Pure question/answer builder for a FEN (no DB, no random).

    Raises ValueError when the position is not a valid puzzle: White
    must be in check, it must not be checkmate, and at least one legal
    escape must exist.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    if board.turn != chess.WHITE:
        raise ValueError("side_to_move_must_be_white")
    if not board.is_check():
        raise ValueError("position_not_in_check")
    if board.is_checkmate():
        raise ValueError("position_is_checkmate")
    moves = escaping_moves(fen)
    if not moves:
        raise ValueError("no_escaping_moves")
    if family is None:
        family = "double" if len(board.checkers()) > 1 else "single"
    return {
        "fen": fen,
        "moves": moves,
        "family": family,
        "prompt_fa": PROMPT_FA,
        "explanation": explanation_for(moves, family),
        "hint_json": {"hints": [{"id": "h1", "text_fa": HINT_FA, "rating_cost": 5}]},
    }


def ensure_exercise(db: Session) -> None:
    exercise = db.get(Exercise, SLUG)
    if exercise is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa=TITLE_FA,
                title_en="Get Out of Check",
                description="تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.",
                is_active=True,
                sort_order=SORT_ORDER,
            )
        )
        db.commit()
    elif exercise.title_fa != TITLE_FA or exercise.sort_order != SORT_ORDER:
        # Roadmap/title fix: the official Persian title is «رفع کیش».
        exercise.title_fa = TITLE_FA
        exercise.sort_order = SORT_ORDER
        db.commit()


def _match_existing(db: Session, fen: str, exclude_ids: set[int]) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists)."""
    candidates = (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == SLUG,
            Puzzle.is_published == True,  # noqa: E712
            Puzzle.is_archived == False,  # noqa: E712
            Puzzle.fen == fen,
        )
        .order_by(Puzzle.id)
        .all()
    )
    usable: Puzzle | None = None
    identical = False
    for puzzle in candidates:
        identical = True
        if usable is None and puzzle.id not in exclude_ids:
            usable = puzzle
    return usable, identical


def _rating_for(moves: list[str], rng: random.Random) -> float:
    base = 800.0 + len(moves) * 25.0 + rng.randrange(0, 60)
    return float(max(700.0, min(1300.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
) -> Puzzle:
    """Generate one verified question and persist it as a published puzzle.

    The answer set stays derivable: only the FEN is stored (server-side
    ``answer_json``), never a move list.
    """
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng)
    usable, identical = _match_existing(db, data["fen"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng)
            usable, identical = _match_existing(db, data["fen"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={"fen": data["fen"]},
        answer_json={"fen": data["fen"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["moves"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
