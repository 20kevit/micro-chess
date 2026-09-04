"""Pathfinding rules: single-step legality plus full-path replay.

The selected piece moves step by step toward a target square. A step is
allowed when it is a legal chess move for that piece (python-chess, with
the mover to move: pins, blocks, pawn rules and king safety included) AND
it satisfies the exercise rule:

- landing on an enemy piece is allowed only as a legal capture
  (captures of the enemy king are never allowed);
- landing on an empty square is allowed only when no enemy attacks it.

Enemy control is recomputed from the board after every move, so captures
change the control map. En passant never arises (enemies are static and
generated positions carry no ep square); the ep square is stripped when
serializing so a stale flag can never enable a phantom capture.
Promotion defaults to queen when a pawn reaches the last rank.
"""

from typing import Any

import chess

from app.modules.rule_engine.base import AttemptResult, ValidationResult, normalize_square

SLUG = "pathfinding"

_PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}


def _promotion_choice(raw: Any) -> chess.PieceType | None:
    if not isinstance(raw, str):
        return None
    return _PROMOTIONS.get(raw.strip().lower())


def _serialize(board: chess.Board, mover: chess.Color) -> str:
    board.turn = mover
    board.ep_square = None
    return board.fen()


def mover_color(fen: str, start: str) -> chess.Color:
    """Color of the piece on the start square. Raises ValueError when empty."""
    board = chess.Board(fen)  # raises on invalid FEN
    piece = board.piece_at(chess.parse_square(start))
    if piece is None:
        raise ValueError("no_piece_on_start_square")
    return piece.color


def iter_moves(fen: str, mover: chess.Color, origin: str):
    """Yield (dest, new_fen, captured_square|None) for every allowed step.

    Single source of truth for the movement rule; used by step validation,
    full-path replay and the generator's reachability check.
    """
    board = chess.Board(fen)  # raises on invalid FEN
    origin_sq = chess.parse_square(origin)
    piece = board.piece_at(origin_sq)
    if piece is None or piece.color != mover:
        return
    board.turn = mover
    enemy = not mover
    for move in board.legal_moves:
        if move.from_square != origin_sq:
            continue
        dest_piece = board.piece_at(move.to_square)
        if dest_piece is not None:
            if dest_piece.color != enemy or dest_piece.piece_type == chess.KING:
                continue
            if not board.is_capture(move):
                continue
        elif board.is_attacked_by(enemy, move.to_square):
            continue
        probe = board.copy(stack=False)
        probe.push(move)
        captured = chess.square_name(move.to_square) if dest_piece is not None else None
        yield chess.square_name(move.to_square), _serialize(probe, mover), captured


def apply_step(
    fen: str,
    mover: chess.Color,
    origin: str,
    dest: str,
    promotion: Any = None,
) -> dict[str, Any] | None:
    """Apply one step. Returns {"fen", "captured"} or None when forbidden.

    Raises ValueError on invalid FEN or square names.
    """
    origin_sq = chess.parse_square(origin)
    dest_sq = chess.parse_square(dest)
    if origin_sq == dest_sq:
        return None
    matches = [
        (square, new_fen, captured)
        for (square, new_fen, captured) in iter_moves(fen, mover, origin)
        if square == chess.square_name(dest_sq)
    ]
    if not matches:
        return None
    # Pawn promotion: the client sends its choice, defaulting to queen.
    board = chess.Board(fen)
    board.turn = mover
    probe_moves = [
        m for m in board.legal_moves if m.from_square == origin_sq and m.to_square == dest_sq
    ]
    if any(m.promotion is not None for m in probe_moves):
        promo = _promotion_choice(promotion) or chess.QUEEN
        if not any(m.promotion == promo for m in probe_moves):
            return None
    _, new_fen, captured = matches[0]
    return {"fen": new_fen, "captured": captured}


def replay_path(
    fen: str,
    start: str,
    target: str,
    path: list[str],
    promotion: Any = None,
) -> dict[str, Any]:
    """Replay a full path from the initial position.

    Returns {"ok", "prefix", "fail_at", "reached", "moves"}. Raises
    ValueError on invalid FEN or start square.
    """
    mover = mover_color(fen, start)
    prefix = [start]
    current_fen = fen
    current = start
    for square in path[1:]:
        nxt = apply_step(current_fen, mover, current, square, promotion)
        if nxt is None:
            return {
                "ok": False,
                "prefix": prefix,
                "fail_at": square,
                "reached": False,
                "moves": len(prefix) - 1,
            }
        current_fen = nxt["fen"]
        current = square
        prefix.append(square)
    return {
        "ok": current == target,
        "prefix": prefix,
        "fail_at": None if current == target else target,
        "reached": current == target,
        "moves": len(prefix) - 1,
    }


def validate(puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    start = normalize_square(puzzle_answer.get("from")) if isinstance(puzzle_answer, dict) else None
    target = normalize_square(puzzle_answer.get("target")) if isinstance(puzzle_answer, dict) else None
    raw_path = attempt.get("path") if isinstance(attempt, dict) else None
    promotion = attempt.get("promotion") if isinstance(attempt, dict) else None

    def wrong(detail_extra: dict[str, Any] | None = None) -> ValidationResult:
        detail = {"correct": [], "missed": [target] if target else [], "wrong": []}
        if detail_extra:
            detail.update(detail_extra)
        return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)

    if not isinstance(fen, str) or start is None or target is None:
        return wrong()
    if not isinstance(raw_path, list) or not raw_path:
        return wrong()
    path: list[str] = []
    for entry in raw_path:
        square = normalize_square(entry)
        if square is None:
            return wrong({"wrong": [str(entry)]})
        path.append(square)
    if path[0] != start:
        return wrong({"wrong": [path[0]]})
    try:
        run = replay_path(fen, start, target, path, promotion)
    except ValueError:
        return wrong()
    if run["ok"]:
        return ValidationResult(
            result=AttemptResult.CORRECT,
            message_key="feedback.correct",
            detail={
                "correct": run["prefix"],
                "missed": [],
                "wrong": [],
                "reached": True,
                "moves": run["moves"],
            },
        )
    detail: dict[str, Any] = {
        "correct": run["prefix"],
        "missed": [] if run["reached"] else [target],
        "wrong": [run["fail_at"]] if run["fail_at"] else [],
        "reached": run["reached"],
        "moves": run["moves"],
    }
    return ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail=detail)
