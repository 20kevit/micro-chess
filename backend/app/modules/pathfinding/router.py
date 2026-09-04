"""Pathfinding step route: thin wiring, logic lives in validator."""

import chess
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.pathfinding import schemas
from app.modules.pathfinding.validator import SLUG, apply_step, mover_color
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import normalize_square

router = APIRouter(prefix="/pathfinding", tags=["pathfinding"])


def _reject(fen: str, selected_at: str) -> schemas.StepOut:
    return schemas.StepOut(
        ok=False,
        fen=fen,
        selected_at=selected_at,
        reached=False,
        captured=None,
        message_key="pathfinding.invalid",
    )


@router.post("/step", response_model=schemas.StepOut)
def validate_step(body: schemas.StepIn, db: Session = Depends(get_db)):
    puzzle: Puzzle | None = db.get(Puzzle, body.puzzle_id)
    if (
        puzzle is None
        or not puzzle.is_published
        or puzzle.is_archived
        or puzzle.exercise_slug != SLUG
    ):
        raise HTTPException(status_code=404, detail="puzzle_not_available")

    answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
    target = answer.get("target")
    selected_start = answer.get("from")
    selected_at = normalize_square(body.selected_at)
    origin = normalize_square(body.from_square)
    dest = normalize_square(body.to_square)
    if selected_at is None or origin is None or dest is None:
        return _reject(body.fen, body.selected_at)
    if origin != selected_at:
        # Only the selected piece moves; anything else is not a step.
        return _reject(body.fen, body.selected_at)
    try:
        mover = mover_color(answer.get("fen", ""), selected_start or "")
        initial = chess.Board(answer.get("fen", ""))
        selected_piece = initial.piece_at(chess.parse_square(selected_start or ""))
        current = chess.Board(body.fen)
        moving_piece = current.piece_at(chess.parse_square(origin))
    except ValueError:
        return _reject(body.fen, body.selected_at)
    if (
        selected_piece is None
        or moving_piece is None
        or moving_piece.piece_type != selected_piece.piece_type
        or moving_piece.color != selected_piece.color
    ):
        return _reject(body.fen, body.selected_at)

    outcome = None
    try:
        outcome = apply_step(body.fen, mover, origin, dest, body.promotion)
    except ValueError:
        outcome = None
    if outcome is None:
        return _reject(body.fen, body.selected_at)
    return schemas.StepOut(
        ok=True,
        fen=outcome["fen"],
        selected_at=dest,
        reached=dest == target,
        captured=outcome["captured"],
        message_key="",
    )
