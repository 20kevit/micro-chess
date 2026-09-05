"""Rule of the Square validator: can the defending king catch the pawn?

Verdict: exact optimal race play for the lone king-versus-pawn race
(exhaustive game solving over a few thousand states: the pawn pushes,
the king chases; promotion ends the race). For a lone pawn this coincides
with the classical Rule of the Square on every teachable position, and it
additionally adjudicates tempo corners exactly where the naive drawing
misleads (e.g. a king on the square's edge with the attacker to move).
No engine, no tablebase, no heuristics, no external data.

The classical square itself is still computed for every puzzle: it drives
the post-submit visualization and the Persian explanations, and the seed
set is constrained (and tested) so the drawn square always agrees with
the verdict. MVP positions hold exactly one pawn; anything else fails
safe as WRONG.

Puzzle definition (stored in the puzzle row):
- answer_json: {"fen": "..."} (never exposed; the expected answer is
  recomputed from it on every submission).
- position_json: {"mode": "square-rule"} (visible; the board itself is
  rendered from the ``Puzzle.fen`` column, which the exercise needs).
- The ``Puzzle.fen`` column holds the position (the user must see it).

Attempt model (sent by client):
    {"answer": "CAN_CATCH"}  (or "CANNOT_CATCH"; case-insensitive)

Result rules: CORRECT or WRONG only (a classification cannot be partial).
Malformed input fails safely as WRONG and never crashes the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "rule-of-the-square"

CAN_CATCH = "CAN_CATCH"
CANNOT_CATCH = "CANNOT_CATCH"


def square_squares(pawn_square: str, pawn_is_white: bool) -> set[str]:
    """Squares of the pawn's square (borders included, clipped to board).

    A pawn on its starting rank may double-step, so the zone is drawn as
    if it already stood one rank ahead. Used for the post-submit
    visualization and explanations; see ``race_catches_pawn`` for why the
    verdict itself is computed by exact race play.
    """
    sq = chess.parse_square(pawn_square)
    rank = chess.square_rank(sq) + 1
    if not 2 <= rank <= 7:
        raise ValueError(f"pawn_off_board:{pawn_square}")
    file0 = chess.square_file(sq)
    if pawn_is_white:
        started = rank == 2
        side = 8 - rank - (1 if started else 0)
        low = rank + (1 if started else 0)
        files = range(max(1, file0 + 1 - side), min(8, file0 + 1 + side) + 1)
        ranks = range(low, 9)
    else:
        started = rank == 7
        side = rank - 1 - (1 if started else 0)
        high = rank - (1 if started else 0)
        files = range(max(1, file0 + 1 - side), min(8, file0 + 1 + side) + 1)
        ranks = range(1, high + 1)
    return {f"{chr(ord('a') + f - 1)}{r}" for f in files for r in ranks}


def _adjacent_to_square(king_square: str, square: set[str]) -> bool:
    king = chess.parse_square(king_square)
    for sq in square:
        if chess.square_distance(king, chess.parse_square(sq)) == 1:
            return True
    return False


def race_catches_pawn(board: chess.Board) -> bool:
    """Exact lone-pawn race outcome from this position (defender to catch).

    Exhaustive recursion: the pawn side only pushes (captures are
    impossible with minimum material), the defender only walks his king;
    the pawn capturing... the defender wins by landing on the pawn, and
    loses the moment it promotes. Assumes a legal quiet race position
    (no checks, kings apart), which the seed set guarantees.
    """
    pawn_sq = next(
        sq for sq in chess.SQUARES if (p := board.piece_at(sq)) is not None and p.piece_type == chess.PAWN
    )
    pawn_color = board.piece_at(pawn_sq).color
    defender = not pawn_color
    king_sq = next(
        sq
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None and p.piece_type == chess.KING and p.color == defender
    )
    memo: dict[tuple[int | None, int, bool], bool] = {}

    def solve(psq: int | None, ksq: int, turn: bool) -> bool:
        key = (psq, ksq, turn)
        if key in memo:
            return memo[key]
        if psq is None:
            memo[key] = True  # pawn captured
            return True
        rank = chess.square_rank(psq)
        if (pawn_color == chess.WHITE and rank == 7) or (pawn_color == chess.BLACK and rank == 0):
            memo[key] = False  # promoted
            return False
        if turn != pawn_color:
            result = any(
                to == psq or solve(psq, to, pawn_color)
                for to in chess.SquareSet(chess.BB_KING_ATTACKS[ksq])
            )
        else:
            file_index = chess.square_file(psq)
            direction = 1 if pawn_color == chess.WHITE else -1
            pushes = [chess.square(file_index, rank + direction)]
            if (pawn_color == chess.WHITE and rank == 1) or (pawn_color == chess.BLACK and rank == 6):
                pushes.append(chess.square(file_index, rank + 2 * direction))
            result = all(solve(o, ksq, defender) for o in pushes)
        memo[key] = result
        return result

    return solve(pawn_sq, king_sq, board.turn)


def evaluate(fen: str) -> dict[str, Any]:
    """Authoritative classification for a position. Raises ValueError."""
    board = chess.Board(fen)  # raises on invalid FEN
    pawns = [
        chess.square_name(sq)
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) is not None and p.piece_type == chess.PAWN
    ]
    if len(pawns) != 1:
        raise ValueError(f"expected exactly one pawn, got {len(pawns)}")
    pawn_square = pawns[0]
    pawn_is_white = board.piece_at(chess.parse_square(pawn_square)).color == chess.WHITE
    defender_color = not pawn_is_white
    king_square = next(
        (
            chess.square_name(sq)
            for sq in chess.SQUARES
            if (p := board.piece_at(sq)) is not None
            and p.piece_type == chess.KING
            and p.color == defender_color
        ),
        None,
    )
    if king_square is None:
        raise ValueError("missing_defending_king")

    square = square_squares(pawn_square, pawn_is_white)
    inside = king_square in square
    steps_in = race_catches_pawn(board)
    files = sorted({s[0] for s in square})
    ranks = sorted({int(s[1]) for s in square})
    corners = sorted({f"{f}{r}" for f in (files[0], files[-1]) for r in (ranks[0], ranks[-1])})
    return {
        "expected": CAN_CATCH if steps_in else CANNOT_CATCH,
        "inside": inside,
        "pawn": pawn_square,
        "pawn_is_white": pawn_is_white,
        "king": king_square,
        "turn_is_white": board.turn == chess.WHITE,
        "square": sorted(square),
        "corners": corners,
    }


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    fen = answer.get("fen")
    raw = attempt_map.get("answer")
    submitted = raw.strip().upper() if isinstance(raw, str) else ""

    try:
        info = evaluate(fen) if isinstance(fen, str) else None
    except ValueError:
        info = None
    if info is None:
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={"correct": [], "missed": [], "wrong": [submitted] if submitted else []},
        )

    expected: str = info["expected"]
    if submitted not in (CAN_CATCH, CANNOT_CATCH):
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={
                "correct": [],
                "missed": [expected],
                "wrong": [submitted] if submitted else [],
                "expected": expected,
                "square": info["square"],
                "corners": info["corners"],
            },
        )
    if submitted == expected:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={
                "correct": [expected],
                "missed": [],
                "wrong": [],
                "expected": expected,
                "square": info["square"],
                "corners": info["corners"],
            },
        )
    return ValidationResult(
        result=AttemptResult.WRONG,
        message_key="feedback.wrong",
        detail={
            "correct": [],
            "missed": [expected],
            "wrong": [submitted],
            "expected": expected,
            "square": info["square"],
            "corners": info["corners"],
        },
    )
