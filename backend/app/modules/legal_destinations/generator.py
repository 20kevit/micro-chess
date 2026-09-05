"""Exercise 2 question generator: dynamic white-only positions.

Flow per new puzzle::

    1. Pick a target piece type uniformly (pawn/knight/bishop/rook/queen/king).
    2. Place it on a random legal square (pawns never on rank 1/8).
    3. Place exactly one white king (the target itself when it is a king)
       plus 2-6 white blocker pieces, deliberately positioned so paths are
       sometimes interrupted (ray blockers, knight-destination occupants,
       king neighbours, pawn blocks).
    4. Compute the authoritative destinations server-side via
       ``legal_destinations`` with the IGNORE_ENEMY_ATTACKS profile:
       the board holds only white pieces, so there is no opponent attack
       map to consult and no check/king-safety scenarios to invent.
    5. Build the Persian prompt/explanation/hint and persist a published
       ``Puzzle`` row. The answer lives only in ``answer_json`` and is never
       sent to the client (see ``PuzzleOut``).

No black pieces are generated (in particular no black king); python-chess
still parses the FEN and generates pseudo-legal movement for the target.
"""

from __future__ import annotations

import random

import chess
from sqlalchemy.orm import Session

from app.modules.exercises.models import Exercise
from app.modules.legal_destinations.validator import (
    IGNORE_ENEMY_ATTACKS,
    SLUG,
    legal_destinations,
)
from app.modules.puzzles.models import Puzzle

PROFILE = IGNORE_ENEMY_ATTACKS

PIECE_TYPES = ["p", "n", "b", "r", "q", "k"]

PIECE_NAMES_FA = {
    "p": "سرباز",
    "n": "اسب",
    "b": "فیل",
    "r": "رخ",
    "q": "وزیر",
    "k": "شاه",
}

PIECE_HINTS_FA = {
    "p": "سرباز سفید فقط جلو می‌رود؛ مورب خالی مقصد نیست.",
    "n": "اسب به شکل L می‌پرد و از روی مهره‌ها رد می‌شود.",
    "b": "فیل فقط مورب می‌رود و از مهره خودی رد نمی‌شود.",
    "r": "رخ فقط صاف می‌رود و از مهره خودی رد نمی‌شود.",
    "q": "وزیر مثل رخ و فیل با هم حرکت می‌کند.",
    "k": "شاه فقط یک خانه به اطراف می‌رود.",
}

BLOCKER_KINDS = ["p", "n", "b", "r", "q"]

_FILES = "abcdefgh"

# Sliding directions as (df, dr).
_ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

_MAX_GENERATION_ATTEMPTS = 50


def _sq_name(file_idx: int, rank_idx: int) -> str | None:
    if 0 <= file_idx < 8 and 0 <= rank_idx < 8:
        return f"{_FILES[file_idx]}{rank_idx + 1}"
    return None


def _sq_parts(sq: str) -> tuple[int, int]:
    return _FILES.index(sq[0]), int(sq[1]) - 1


def _knight_targets(sq: str) -> list[str]:
    f, r = _sq_parts(sq)
    out = []
    for df, dr in ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)):
        name = _sq_name(f + df, r + dr)
        if name:
            out.append(name)
    return out


def _king_targets(sq: str) -> list[str]:
    f, r = _sq_parts(sq)
    out = []
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            name = _sq_name(f + df, r + dr)
            if name:
                out.append(name)
    return out


def _ray_squares(sq: str, dirs: list[tuple[int, int]]) -> list[str]:
    f, r = _sq_parts(sq)
    out = []
    for df, dr in dirs:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            out.append(f"{_FILES[nf]}{nr + 1}")
            nf += df
            nr += dr
    return out


def _slider_dirs(piece_type: str) -> list[tuple[int, int]]:
    if piece_type == "b":
        return _BISHOP_DIRS
    if piece_type == "r":
        return _ROOK_DIRS
    return _ROOK_DIRS + _BISHOP_DIRS


def _random_free_square(rng: random.Random, occupied: set[str], *, for_pawn: bool = False) -> str:
    for _ in range(100):
        f = rng.randrange(8)
        r = rng.randrange(8)
        if for_pawn and (r == 0 or r == 7):
            continue
        name = f"{_FILES[f]}{r + 1}"
        if name not in occupied:
            return name
    # Fallback: first free square (scan order); callers guarantee space.
    for r in range(8):
        for f in range(8):
            if for_pawn and (r == 0 or r == 7):
                continue
            name = f"{_FILES[f]}{r + 1}"
            if name not in occupied:
                return name
    raise ValueError("board_full")


def _build_fen(target_type: str, target_sq: str, extra_white: dict[str, str]) -> str:
    board = chess.Board.empty()
    symbol_map = {"p": "P", "n": "N", "b": "B", "r": "R", "q": "Q", "k": "K"}
    board.set_piece_at(chess.parse_square(target_sq), chess.Piece.from_symbol(symbol_map[target_type]))
    for sq, kind in extra_white.items():
        board.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(symbol_map[kind]))
    board.turn = chess.WHITE
    board.set_castling_fen("-")
    board.ep_square = None
    board.halfmove_clock = 0
    board.fullmove_number = 1
    return board.fen()


def prompt_for_piece(piece_type: str) -> str:
    """Persian question text for a target piece type."""
    return f"این {PIECE_NAMES_FA[piece_type]} به چه خانه‌هایی می‌تواند برود؟"


def explanation_for(piece_type: str, from_sq: str, squares: list[str]) -> str:
    name = PIECE_NAMES_FA[piece_type]
    if not squares:
        return f"این {name} در {from_sq} هیچ مقصد قانونی ندارد؛ پس هیچ خانه‌ای انتخاب نکن."
    return f"این {name} در {from_sq} می‌تواند به {len(squares)} خانه برود."


def question_for_position(fen: str, from_sq: str, profile: str = PROFILE) -> dict:
    """Pure question/answer builder for a FEN + target square (no DB, no random)."""
    squares = legal_destinations(fen, from_sq, profile)
    board = chess.Board(fen)
    piece = board.piece_at(chess.parse_square(from_sq))
    piece_type = piece.symbol().lower() if piece else "p"
    return {
        "fen": fen,
        "from": from_sq,
        "profile": profile,
        "piece_type": piece_type,
        "squares": squares,
        "prompt_fa": prompt_for_piece(piece_type),
        "explanation": explanation_for(piece_type, from_sq, squares),
        "hint_json": {"hints": [{"id": "h1", "text_fa": PIECE_HINTS_FA[piece_type], "rating_cost": 5}]},
    }


def generate_position_data(
    rng: random.Random | None = None,
    piece_type: str | None = None,
) -> dict:
    """Generate one random white-only position with an interesting target.

    Raises ValueError after bounded retries if nothing valid emerges.
    """
    rng = rng if rng is not None else random
    if piece_type is not None and piece_type not in PIECE_TYPES:
        raise ValueError("unknown_piece_type")
    for _ in range(_MAX_GENERATION_ATTEMPTS):
        ptype = piece_type or rng.choice(PIECE_TYPES)
        occupied: set[str] = set()
        target_sq = _random_free_square(rng, occupied, for_pawn=(ptype == "p"))
        occupied.add(target_sq)
        extra: dict[str, str] = {}

        # Exactly one white king on the board.
        if ptype != "k":
            king_sq = _random_free_square(rng, occupied)
            occupied.add(king_sq)
            extra[king_sq] = "k"

        # Deliberate blockers on the target's movement paths so questions
        # are educational rather than empty-board trivialities.
        blocker_count = rng.randint(2, 6)
        candidates: list[str] = []
        if ptype in ("b", "r", "q"):
            rays = _ray_squares(target_sq, _slider_dirs(ptype))
            # Prefer near blockers (distance 1-3) that visibly cut rays.
            f0, r0 = _sq_parts(target_sq)
            near = [s for s in rays if max(abs(_FILES.index(s[0]) - f0), abs(int(s[1]) - 1 - r0)) <= 3]
            candidates = near or rays
        elif ptype == "n":
            candidates = _knight_targets(target_sq)
        elif ptype == "k":
            candidates = _king_targets(target_sq)
        elif ptype == "p":
            f, r = _sq_parts(target_sq)
            ahead = _sq_name(f, r + 1)
            ahead2 = _sq_name(f, r + 2) if r == 1 else None
            if ahead:
                candidates = [ahead] + ([ahead2] if ahead2 else [])

        rng.shuffle(candidates)
        # Pawns: sometimes blocked ahead, sometimes open / double-step.
        if ptype == "p":
            want_block = rng.random() < 0.45
            placed_block = False
            if want_block and candidates:
                sq = candidates[0]
                if sq not in occupied:
                    extra[sq] = rng.choice(BLOCKER_KINDS)
                    occupied.add(sq)
                    placed_block = True
            # Fill the rest randomly (avoid the square directly ahead when
            # we want an open pawn, so one/two-step situations appear).
            for _ in range(blocker_count - (1 if placed_block else 0)):
                sq = _random_free_square(rng, occupied, for_pawn=False)
                # Pawns cannot sit on rank 1/8.
                if sq[1] in ("1", "8"):
                    continue
                extra[sq] = rng.choice(BLOCKER_KINDS)
                occupied.add(sq)
        else:
            # Occupy 1-2 movement squares directly, rest random.
            direct = 0
            if candidates and rng.random() < 0.7:
                direct = rng.randint(1, min(2, len(candidates), blocker_count))
                for sq in candidates[:direct]:
                    if sq in occupied:
                        continue
                    kind = rng.choice(BLOCKER_KINDS)
                    if kind == "p" and sq[1] in ("1", "8"):
                        kind = rng.choice(["n", "b", "r", "q"])
                    extra[sq] = kind
                    occupied.add(sq)
            for _ in range(blocker_count - direct):
                sq = _random_free_square(rng, occupied)
                kind = rng.choice(BLOCKER_KINDS)
                if kind == "p" and sq[1] in ("1", "8"):
                    kind = rng.choice(["n", "b", "r", "q"])
                extra[sq] = kind
                occupied.add(sq)

        fen = _build_fen(ptype, target_sq, extra)
        try:
            squares = legal_destinations(fen, target_sq, PROFILE)
        except ValueError:
            continue
        # Zero-target positions are valid but must stay rare.
        if not squares and rng.random() > 0.15:
            continue
        return {
            "fen": fen,
            "from": target_sq,
            "profile": PROFILE,
            "piece_type": ptype,
            "squares": squares,
        }
    raise ValueError("generation_failed")


def generate_question_data(
    rng: random.Random | None = None,
    piece_type: str | None = None,
) -> dict:
    """Pick a random position and build its full question/answer data."""
    rng = rng if rng is not None else random
    pos = generate_position_data(rng, piece_type)
    return question_for_position(pos["fen"], pos["from"], pos["profile"])


def ensure_exercise(db: Session) -> None:
    if db.get(Exercise, SLUG) is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="مقصدهای قانونی",
                title_en="Legal Destinations",
                description="مقصدهای قانونی مهره مشخص‌شده را پیدا کن.",
                is_active=True,
                sort_order=1,
            )
        )
        db.commit()


def _match_existing(
    db: Session, fen: str, from_sq: str, exclude_ids: set[int]
) -> tuple[Puzzle | None, bool]:
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
        position = puzzle.position_json if isinstance(puzzle.position_json, dict) else {}
        if position.get("from") != from_sq:
            continue
        identical = True
        if usable is None and puzzle.id not in exclude_ids:
            usable = puzzle
    return usable, identical


def _rating_for(squares: list[str], rng: random.Random) -> float:
    base = 750.0 + len(squares) * 12.0 + rng.randrange(0, 60)
    return float(max(700.0, min(1250.0, base)))


def create_puzzle(
    db: Session,
    rng: random.Random | None = None,
    exclude_ids: set[int] | None = None,
    piece_type: str | None = None,
) -> Puzzle:
    """Generate one random question and persist it as a published puzzle.

    The persisted row plugs into the standard attempt flow unchanged
    (``POST /api/v1/attempts`` validates against the stored ``answer_json``).
    Identical (position, target) rows are reused, not duplicated;
    ``exclude_ids`` steers away from just-shown puzzles: a novel combo is
    created immediately, an excluded duplicate triggers a re-roll
    (bounded; best-effort).
    """
    rng = rng if rng is not None else random
    ensure_exercise(db)
    excluded = set(exclude_ids or [])
    data = generate_question_data(rng, piece_type)
    usable, identical = _match_existing(db, data["fen"], data["from"], excluded)
    if usable is not None:
        return usable
    if identical:
        for _ in range(10):
            data = generate_question_data(rng, piece_type)
            usable, identical = _match_existing(db, data["fen"], data["from"], excluded)
            if usable is not None:
                return usable
            if not identical:
                break
    puzzle = Puzzle(
        exercise_slug=SLUG,
        fen=data["fen"],
        position_json={"from": data["from"], "profile": data["profile"]},
        answer_json={"squares": data["squares"], "from": data["from"], "profile": data["profile"]},
        hint_json=data["hint_json"],
        prompt_fa=data["prompt_fa"],
        explanation=data["explanation"],
        initial_rating=_rating_for(data["squares"], rng),
        is_published=True,
        is_archived=False,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle
