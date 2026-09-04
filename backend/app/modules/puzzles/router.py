"""Puzzle routes: read-only for MVP (admin comes later)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.puzzles import service
from app.modules.puzzles.models import Puzzle
from app.modules.puzzles.schemas import PuzzleOut

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


@router.get("", response_model=list[PuzzleOut])
def list_puzzles(exercise: str | None = None, db: Session = Depends(get_db)):
    return service.visible_query(db, exercise).order_by(Puzzle.id).all()
