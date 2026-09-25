"""Exercise 3 question generator: one white hunter vs 3-8 black pieces.

No king hunters: a king cannot capture a defended piece, which would
conflict with this exercise's explicit rule that defense never matters.
Hunter kinds are pawn/knight/bishop/rook/queen only.

Flow per new puzzle::

    1. Pick a hunter piece type uniformly (pawn/knight/bishop/rook/queen).
    2. Place the single WHITE hunter on a random square (pawns never on
       rank 1/8). No other white pieces: no kings, no friendlies — the
       spec forbids them unless the rules require them, and nothing here
       does (there is no check without kings, so no king-safety scenarios
       can arise).
    3. Place 3-8 BLACK pieces with deliberate patterns per hunter kind:
       - sliders (bishop/rook/queen): 1-2 capturable targets on rays, often
         with a shielded (non-capturable) piece behind the first capture,
         plus off-ray decoys that merely look close;
       - knight: 1-2 pieces on valid L-destinations plus nearby-but-invalid
         decoys (blocks never matter for knight jumps);
       - pawn: 1-2 diagonal enemies, often a piece directly ahead (which is
         NOT a capture), plus elsewhere decoys.
    4. Compute the authoritative captures server-side via
       ``capturable_squares`` with the IGNORE_ENEMY_ATTACKS profile: movement
       and blocking apply, but enemy attack maps are never consulted, so a
       defended black piece stays a correct answer and the exercise never
       becomes a king-safety puzzle.
    5. A small fraction of puzzles are zero-capture (nothing capturable);
       submitting an empty selection there is CORRECT (+5).
    6. Build the Persian prompt/explanation/hint and stage a validated
       ``Puzzle`` row. The answer lives only in ``answer_json`` and is never
       sent to the client (see ``PuzzleOut``).

Placement is constructive (deliberate skeleton per kind) but every puzzle
is VERIFIED by recomputing the answer: acceptance requires the intended
capture set (non-empty, or empty for zero-capture mode) and 3-8 black
pieces. Generation retries a bounded number of times, then raises.
"""

from __future__ import annotations

import random

import chess
from sqlalchemy.orm import Session

from app.modules.captures.validator import (
    IGNORE_ENEMY_ATTACKS,
    SLUG,
    capturable_squares,
)
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import SOURCE_GENERATED, Puzzle
from app.modules.puzzles.service import reusable_candidate_query, stage_validated_puzzle

PROFILE = IGNORE_ENEMY_ATTACKS

PIECE_TYPES = ["p", "n", "b", "r", "q"]

PIECE_NAMES_FA = {
    "p": "سرباز",
    "n": "اسب",
    "b": "فیل",
    "r": "رخ",
    "q": "وزیر",
}

PIECE_HINTS_FA = {
    "p": "سرباز سفید فقط مورب جلو می‌زند؛ مهره‌ای که مستقیم جلویش است قابل زدن نیست.",
    "n": "اسب به شکل L می‌پرد و از روی مهره‌ها رد می‌شود؛ خانه‌های نزدیک دیگر جواب نیست.",
    "b": "فیل فقط روی قطر می‌زند و از روی مهره رد نمی‌شود؛ پشت اولین مهره چیزی زده نمی‌شود.",
    "r": "رخ فقط صاف می‌زند و از روی مهره رد نمی‌شود؛ پشت اولین مهره چیزی زده نمی‌شود.",
    "q": "وزیر هم مثل رخ و هم مثل فیل می‌زند.",
}

# Black decoy/target kinds. No black king: capturing a king is outside the
# simplified movement model, and no kings at all means no check scenarios.
BLACK_KINDS = ["p", "n", "b", "r", "q"]

MIN_BLACK = 3
MAX_BLACK = 8

_FILES = "abcdefgh"

# Sliding directions as (df, dr).
_ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

_MAX_GENERATION_ATTEMPTS = 50
# Fraction of puzzles with intentionally zero captures.
_ZERO_TARGET_PROBABILITY = 0.12


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


def _pawn_capture_targets(sq: str) -> list[str]:
    """White pawn diagonal capture squares (forward only)."""
    f, r = _sq_parts(sq)
    out = []
    for df in (-1, 1):
        name = _sq_name(f + df, r + 1)
        if name:
            out.append(name)
    return out


def _ray_from(sq: str, df: int, dr: int) -> list[str]:
    """Squares outward from sq along one direction (nearest first)."""
    f, r = _sq_parts(sq)
    out = []
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


def _random_black_kind(rng: random.Random, sq: str) -> str:
    kind = rng.choice(BLACK_KINDS)
    if kind == "p" and sq[1] in ("1", "8"):
        kind = rng.choice(["n", "b", "r", "q"])
    return kind


def _build_fen(hunter_type: str, hunter_sq: str, black: dict[str, str]) -> str:
    board = chess.Board.empty()
    board.set_piece_at(chess.parse_square(hunter_sq), chess.Piece.from_symbol(hunter_type.upper()))
    for sq, kind in black.items():
        board.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(kind.lower()))
    board.turn = chess.WHITE
    board.set_castling_fen("-")
    board.ep_square = None
    board.halfmove_clock = 0
    board.fullmove_number = 1
    return board.fen()


def prompt_for_piece(piece_type: str) -> str:
    """Persian question text for a hunter piece type."""
    return f"کدام مهره‌های سیاه را می‌توان با این {PIECE_NAMES_FA[piece_type]} زد؟"


def explanation_for(piece_type: str, from_sq: str, squares: list[str]) -> str:
    name = PIECE_NAMES_FA[piece_type]
    if not squares:
        return f"این {name} در {from_sq} هیچ مهره سیاهی را نمی‌تواند بزند؛ پس هیچ خانه‌ای انتخاب نکن."
    return f"این {name} در {from_sq} می‌تواند {len(squares)} مهره سیاه بزند."


def question_for_position(fen: str, from_sq: str, profile: str = PROFILE) -> dict:
    """Pure question/answer builder for a FEN + hunter square (no DB, no random)."""
    squares = capturable_squares(fen, from_sq, profile)
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


def _random_free_square(rng: random.Random, occupied: set[str]) -> str:
    for _ in range(100):
        name = f"{_FILES[rng.randrange(8)]}{rng.randrange(8) + 1}"
        if name not in occupied:
            return name
    for r in range(8):
        for f in range(8):
            name = f"{_FILES[f]}{r + 1}"
            if name not in occupied:
                return name
    raise ValueError("board_full")


def _place(black: dict[str, str], occupied: set[str], sq: str | None, rng: random.Random) -> bool:
    """Place a random black piece on sq. Returns False when sq is unusable."""
    if sq is None or sq in occupied:
        return False
    black[sq] = _random_black_kind(rng, sq)
    occupied.add(sq)
    return True


def _skeleton_slider(
    rng: random.Random,
    hunter_sq: str,
    piece_type: str,
    black: dict[str, str],
    occupied: set[str],
    *,
    zero_target: bool,
) -> None:
    dirs = _slider_dirs(piece_type)
    rays = [(df, dr, _ray_from(hunter_sq, df, dr)) for df, dr in dirs]
    rays = [(df, dr, ray) for df, dr, ray in rays if ray]
    if zero_target:
        # Every black piece stays off the hunter's rays: nothing capturable.
        ray_squares = {sq for _, _, ray in rays for sq in ray}
        candidates = [s for s in chess.SQUARES if (n := chess.square_name(s)) not in occupied and n not in ray_squares]
        rng.shuffle(candidates)
        for s in candidates[: rng.randint(MIN_BLACK, MAX_BLACK)]:
            _place(black, occupied, chess.square_name(s), rng)
        return
    # 1-2 rays carry a capturable target, often with a shielded piece behind.
    rng.shuffle(rays)
    for _, _, ray in rays[: rng.randint(1, 2)]:
        if len(ray) < 1:
            continue
        target_idx = rng.randrange(len(ray))
        _place(black, occupied, ray[target_idx], rng)
        if target_idx + 1 < len(ray) and rng.random() < 0.6:
            behind_idx = rng.randrange(target_idx + 1, len(ray))
            _place(black, occupied, ray[behind_idx], rng)
    # Off-ray decoys: close-looking but never capturable.
    ray_squares = {sq for _, _, ray in rays for sq in ray}
    candidates = [s for s in chess.SQUARES if (n := chess.square_name(s)) not in occupied and n not in ray_squares]
    rng.shuffle(candidates)
    for s in candidates[: rng.randint(0, 2)]:
        _place(black, occupied, chess.square_name(s), rng)


def _skeleton_knight(
    rng: random.Random,
    hunter_sq: str,
    black: dict[str, str],
    occupied: set[str],
    *,
    zero_target: bool,
) -> None:
    valid = [s for s in _knight_targets(hunter_sq) if s not in occupied]
    # Nearby-but-invalid decoys: adjacent or two-away squares that are not
    # knight destinations. Blocks never matter; these teach the L shape.
    f0, r0 = _sq_parts(hunter_sq)
    nearby_invalid = []
    for df in range(-2, 3):
        for dr in range(-2, 3):
            if df == 0 and dr == 0:
                continue
            name = _sq_name(f0 + df, r0 + dr)
            if name and name not in occupied and name not in valid:
                nearby_invalid.append(name)
    rng.shuffle(valid)
    rng.shuffle(nearby_invalid)
    if not zero_target:
        for sq in valid[: rng.randint(1, min(2, len(valid) or 1))]:
            _place(black, occupied, sq, rng)
    for sq in nearby_invalid[: rng.randint(1, 3)]:
        _place(black, occupied, sq, rng)


def _skeleton_pawn(
    rng: random.Random,
    hunter_sq: str,
    black: dict[str, str],
    occupied: set[str],
    *,
    zero_target: bool,
) -> None:
    diagonals = [s for s in _pawn_capture_targets(hunter_sq) if s not in occupied]
    f, r = _sq_parts(hunter_sq)
    ahead = _sq_name(f, r + 1)
    if not zero_target:
        rng.shuffle(diagonals)
        for sq in diagonals[: rng.randint(1, min(2, len(diagonals) or 1))]:
            _place(black, occupied, sq, rng)
    # A piece directly ahead is the classic non-capture; elsewhere decoys
    # must avoid the diagonals so they stay non-capturable.
    forbidden = set(diagonals) | ({ahead} if ahead else set())
    if ahead and ahead not in occupied and rng.random() < 0.5:
        _place(black, occupied, ahead, rng)
        forbidden.add(ahead)
    candidates = [
        chess.square_name(s)
        for s in chess.SQUARES
        if (n := chess.square_name(s)) not in occupied and n not in forbidden
    ]
    rng.shuffle(candidates)
    for sq in candidates[: rng.randint(0, 2)]:
        _place(black, occupied, sq, rng)


def _pad_decoys(
    rng: random.Random,
    hunter_type: str,
    hunter_sq: str,
    black: dict[str, str],
    occupied: set[str],
) -> None:
    """Top up to MIN_BLACK pieces without changing the capture set.

    Decoys are drawn from squares the hunter provably cannot capture:
    off-ray squares for sliders, non-L squares for knights, non-diagonal
    squares for pawns.
    """
    if len(black) >= MIN_BLACK:
        return
    if hunter_type in ("b", "r", "q"):
        forbidden = {hunter_sq} | set(occupied)
        for df, dr in _slider_dirs(hunter_type):
            forbidden.update(_ray_from(hunter_sq, df, dr))
    elif hunter_type == "n":
        forbidden = {hunter_sq} | set(occupied) | set(_knight_targets(hunter_sq))
    else:  # pawn
        forbidden = {hunter_sq} | set(occupied) | set(_pawn_capture_targets(hunter_sq))
        f, r = _sq_parts(hunter_sq)
        if (ahead := _sq_name(f, r + 1)):
            forbidden.add(ahead)
    candidates = [
        chess.square_name(s) for s in chess.SQUARES if chess.square_name(s) not in forbidden
    ]
    rng.shuffle(candidates)
    for sq in candidates:
        if len(black) >= MIN_BLACK:
            break
        _place(black, occupied, sq, rng)


def generate_position_data(
    rng: random.Random | None = None,
    piece_type: str | None = None,
    *,
    zero_target: bool | None = None,
) -> dict:
    """Generate one random hunter-vs-black-pieces position.

    The returned answer is recomputed from the board (never assumed from
    the skeleton): non-zero mode requires at least one capture, zero mode
    requires none. Raises ValueError after bounded retries.
    """
    rng = rng if rng is not None else random
    if piece_type is not None and piece_type not in PIECE_TYPES:
        raise ValueError("unknown_piece_type")
    for _ in range(_MAX_GENERATION_ATTEMPTS):
        ptype = piece_type or rng.choice(PIECE_TYPES)
        occupied: set[str] = set()
        # Hunter placement (pawns never on rank 1/8).
        hunter_sq = None
        for _ in range(100):
            candidate = f"{_FILES[rng.randrange(8)]}{rng.randrange(8) + 1}"
            if ptype == "p" and candidate[1] in ("1", "8"):
                continue
            hunter_sq = candidate
            break
        assert hunter_sq is not None
        occupied.add(hunter_sq)
        black: dict[str, str] = {}
        zero = zero_target if zero_target is not None else rng.random() < _ZERO_TARGET_PROBABILITY
        if ptype in ("b", "r", "q"):
            _skeleton_slider(rng, hunter_sq, ptype, black, occupied, zero_target=zero)
        elif ptype == "n":
            _skeleton_knight(rng, hunter_sq, black, occupied, zero_target=zero)
        else:  # pawn
            _skeleton_pawn(rng, hunter_sq, black, occupied, zero_target=zero)
        _pad_decoys(rng, ptype, hunter_sq, black, occupied)
        if not (MIN_BLACK <= len(black) <= MAX_BLACK):
            continue
        fen = _build_fen(ptype, hunter_sq, black)
        try:
            squares = capturable_squares(fen, hunter_sq, PROFILE)
        except ValueError:
            continue
        if zero and squares:
            continue
        if not zero and not squares:
            continue
        return {
            "fen": fen,
            "from": hunter_sq,
            "profile": PROFILE,
            "piece_type": ptype,
            "squares": squares,
            "zero_target": zero,
        }
    raise ValueError("generation_failed")


def generate_question_data(
    rng: random.Random | None = None,
    piece_type: str | None = None,
    *,
    zero_target: bool | None = None,
) -> dict:
    """Pick a random position and build its full question/answer data."""
    rng = rng if rng is not None else random
    pos = generate_position_data(rng, piece_type, zero_target=zero_target)
    return question_for_position(pos["fen"], pos["from"], pos["profile"])


def ensure_exercise(db: Session) -> None:
    if db.get(Exercise, SLUG) is None:
        db.add(
            Exercise(
                slug=SLUG,
                title_fa="گرفتن مهره‌ها",
                title_en="Captures",
                description="مهره‌های سیاهی که مهره سفید می‌تواند بزند را پیدا کن.",
                is_active=True,
                sort_order=2,
            )
        )
        db.commit()


def _match_existing(
    db: Session, fen: str, from_sq: str, exclude_ids: set[int]
) -> tuple[Puzzle | None, bool]:
    """Return (usable_row_or_None, identical_exists)."""
    candidates = (
        reusable_candidate_query(db, SLUG)
        .filter(Puzzle.fen == fen)
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
    *,
    source: str = SOURCE_GENERATED,
    source_reference: str | None = None,
) -> Puzzle:
    """Generate one random question and stage it as a validated candidate.

    The staged row plugs into the standard attempt flow unchanged
    (``POST /api/v1/attempts`` validates against the stored ``answer_json``).
    Identical (position, hunter) rows are reused, not duplicated;
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
    puzzle = stage_validated_puzzle(
        db,
        {
            "exercise_slug": SLUG,
            "fen": data["fen"],
            "position_json": {"from": data["from"], "profile": data["profile"]},
            "answer_json": {"squares": data["squares"], "from": data["from"], "profile": data["profile"]},
            "hint_json": data["hint_json"],
            "prompt_fa": data["prompt_fa"],
            "explanation": data["explanation"],
            "initial_rating": _rating_for(data["squares"], rng),
        },
        source=source,
        source_reference=source_reference
        or (f"generator:{SLUG}" if source == SOURCE_GENERATED else f"{source}:{SLUG}"),
    )
    db.commit()
    db.refresh(puzzle)
    return puzzle
