"""Opening Move Reconstruction validator: rebuild the opening, eyes on boards.

The user sees the TARGET position and replays the opening from the START
position on a second board. Correctness is positional, never textual: the
submitted UCI moves are replayed on a server-side ``python-chess`` board
from the stored start, and the answer counts as CORRECT only when the
resulting position (placement + side to move + castling rights +
en-passant square) equals the stored target. Any move order reaching the
target counts, so alternative lines are accepted by construction; the
stored canonical sequence only feeds feedback text.

Puzzle definition (stored in the puzzle row):
- answer_json: {"start_fen": "...", "target_fen": "...",
  "solutions": [["e2e4", ...]]} (never exposed; validators only receive
  answer_json, and the target comparison never trusts client FENs).
- position_json: {"start_fen": "...", "target_fen": "...",
  "mode": "reconstruct", "opening_fa": "...", "description_fa": "..."}
  (visible to frontend; both FENs are needed to render the two boards,
  but never the solution sequence).
- The ``Puzzle.fen`` column holds the target FEN (the board to explain).

Attempt model (sent by client):
    {"moves": ["e2e4", "e7e5", "g1f3"]}

Result rules: CORRECT or WRONG only (a sequence cannot be partial).
Malformed, illegal, incomplete, extra, or divergent sequences fail safely
as WRONG and never crash the API.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult

SLUG = "opening-move-reconstruction"

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def position_key(fen: str) -> str:
    """Comparable position state: placement + turn + castling + en passant.

    Halfmove/fullmove clocks are intentionally excluded: two histories
    reaching the same chess position are the same reconstruction.
    Raises ValueError on invalid FEN.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    turn = "w" if board.turn == chess.WHITE else "b"
    ep = chess.square_name(board.ep_square) if board.ep_square is not None else "-"
    return f"{board.board_fen()} {turn} {board.castling_xfen()} {ep}"


def play_sequence(start_fen: str, ucis: list[str]) -> chess.Board:
    """Replay UCI moves from a start FEN. Raises ValueError on bad input."""
    board = chess.Board(start_fen)  # raises on invalid FEN
    for raw in ucis:
        if not isinstance(raw, str):
            raise ValueError("non_string_move")
        try:
            move = chess.Move.from_uci(raw.strip())
        except ValueError:
            raise ValueError(f"malformed_move:{raw}")
        if move not in board.legal_moves:
            raise ValueError(f"illegal_move:{raw}")
        board.push(move)
    return board


def sequence_sans(start_fen: str, ucis: list[str]) -> list[str]:
    """Canonical SANs for a UCI sequence (used for feedback/detail)."""
    board = chess.Board(start_fen)  # raises on invalid FEN
    sans: list[str] = []
    for raw in ucis:
        move = chess.Move.from_uci(raw)
        sans.append(board.san(move))
        board.push(move)
    return sans


def matched_plies(canonical: list[str], submitted: list[str]) -> int:
    """Length of the common UCI prefix (feedback only, never correctness)."""
    n = 0
    for a, b in zip(canonical, submitted):
        if a != b:
            break
        n += 1
    return n


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    attempt_map = attempt if isinstance(attempt, dict) else {}
    start_fen = answer.get("start_fen")
    target_fen = answer.get("target_fen")
    raw_solutions = answer.get("solutions")
    raw_moves = attempt_map.get("moves")

    solutions = (
        [list(s) for s in raw_solutions]
        if isinstance(raw_solutions, list) and raw_solutions
        else []
    )
    canonical: list[str] = [m for m in solutions[0]] if solutions else []
    submitted = list(raw_moves) if isinstance(raw_moves, list) else []

    try:
        example_sans = sequence_sans(start_fen, canonical) if isinstance(start_fen, str) else []
    except (ValueError, AssertionError):
        example_sans = []
    expected_key: str | None = None
    try:
        expected_key = position_key(target_fen) if isinstance(target_fen, str) else None
    except ValueError:
        expected_key = None

    def wrong() -> ValidationResult:
        try:
            submitted_sans = sequence_sans(start_fen, [m for m in submitted if isinstance(m, str)])
        except (ValueError, AssertionError):
            submitted_sans = [str(m) for m in submitted]
        return ValidationResult(
            result=AttemptResult.WRONG,
            message_key="feedback.wrong",
            detail={
                "correct": [],
                "missed": example_sans,
                "wrong": submitted_sans,
                "correct_sequence": example_sans,
                "submitted_sequence": submitted_sans,
                "matched_plies": matched_plies(canonical, [m for m in submitted if isinstance(m, str)]),
                "expected_plies": len(canonical),
            },
        )

    # Only the stored position data is authoritative; client-supplied FENs
    # or solutions (if any) are ignored entirely.
    if not isinstance(start_fen, str) or expected_key is None or not canonical:
        return wrong()
    try:
        board = play_sequence(start_fen, submitted)
    except ValueError:
        return wrong()
    try:
        got_key = position_key(board.fen())
    except ValueError:
        return wrong()
    if got_key == expected_key:
        try:
            submitted_sans = sequence_sans(start_fen, submitted)
        except (ValueError, AssertionError):
            submitted_sans = [str(m) for m in submitted]
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={
                "correct": submitted_sans,
                "missed": [],
                "wrong": [],
                "correct_sequence": submitted_sans,
                "submitted_sequence": submitted_sans,
                "matched_plies": len(submitted),
                "expected_plies": len(canonical),
            },
        )
    return wrong()
