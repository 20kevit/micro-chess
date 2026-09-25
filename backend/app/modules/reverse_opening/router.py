"""Reverse Opening step route: thin wiring, logic lives in validator."""

import chess
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.reverse_opening import schemas
from app.modules.reverse_opening.validator import (
    SLUG,
    matched_plies,
    position_key,
)
from app.modules.puzzles import service as puzzle_service
from app.modules.rule_engine.base import normalize_square

router = APIRouter(prefix="/reverse-opening", tags=["reverse-opening"])

_PROMOTIONS = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}


def _reject(fen: str, moves: list[str], message_key: str = "reconstruction.invalid") -> schemas.StepOut:
    return schemas.StepOut(fen=fen, moves=moves, ok=False, on_track=True, message_key=message_key)


@router.post("/step", response_model=schemas.StepOut)
def validate_step(body: schemas.StepIn, db: Session = Depends(get_db)):
    try:
        puzzle = puzzle_service.require_visible_puzzle(db, body.puzzle_id, SLUG)
    except puzzle_service.PlayerPuzzleUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
    start_fen = answer.get("start_fen")
    raw_solutions = answer.get("solutions")
    solutions = [list(s) for s in raw_solutions] if isinstance(raw_solutions, list) and raw_solutions else []
    canonical: list[str] = [m for m in solutions[0]] if solutions else []
    history = [m for m in body.moves if isinstance(m, str)]
    origin = normalize_square(body.from_square)
    dest = normalize_square(body.to_square)

    if not isinstance(start_fen, str) or origin is None or dest is None:
        return _reject(body.fen, history)

    # The claimed history must genuinely replay from the stored start to
    # the claimed position; anything else is rejected (no trust in client
    # FENs). The final submission revalidates the whole sequence anyway.
    try:
        board = chess.Board(start_fen)
        for raw in history:
            move = chess.Move.from_uci(raw.strip())
            if move not in board.legal_moves:
                return _reject(body.fen, history)
            board.push(move)
        if position_key(board.fen()) != position_key(body.fen):
            return _reject(body.fen, history)
    except ValueError:
        return _reject(body.fen, history)

    candidates = [
        m
        for m in board.legal_moves
        if m.from_square == chess.parse_square(origin) and m.to_square == chess.parse_square(dest)
    ]
    if not candidates:
        return _reject(body.fen, history)
    promotion = body.promotion.strip().lower() if isinstance(body.promotion, str) else ""
    if len(candidates) > 1:
        if promotion not in _PROMOTIONS:
            return _reject(body.fen, history, "reconstruction.promotion")
        candidates = [m for m in candidates if m.promotion == _PROMOTIONS[promotion]]
    if len(candidates) != 1:
        return _reject(body.fen, history)
    move = candidates[0]

    san = board.san(move)
    if board.is_en_passant(move):
        captured: str | None = "P"
    else:
        captured_piece = board.piece_at(move.to_square)
        captured = chess.piece_symbol(captured_piece.piece_type).upper() if captured_piece else None
    board.push(move)
    new_history = history + [move.uci()]
    return schemas.StepOut(
        ok=True,
        fen=board.fen(),
        moves=new_history,
        san=san,
        captured=captured,
        on_track=matched_plies(canonical, new_history) == len(new_history),
        message_key="",
    )
