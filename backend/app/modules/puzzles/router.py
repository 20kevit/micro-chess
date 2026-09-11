"""Puzzle routes: read-only for MVP (admin comes later)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery, apply_pagination
from app.modules.puzzles import service
from app.modules.puzzles.models import Puzzle
from app.modules.puzzles.schemas import PuzzleOut

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


@router.get("", response_model=list[PuzzleOut])
def list_puzzles(
    exercise: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
):
    q = service.visible_query(db, exercise).order_by(Puzzle.id)
    return apply_pagination(q, page=page, page_size=page_size).all()


@router.get("/{puzzle_id}", response_model=PuzzleOut)
def get_puzzle(puzzle_id: int, db: Session = Depends(get_db)):
    # Education content stays accessible later for the same puzzle.
    # The definitive answer is never exposed here (see PuzzleOut).
    puzzle = service.visible_query(db).filter(Puzzle.id == puzzle_id).first()
    if puzzle is None:
        raise HTTPException(status_code=404, detail="puzzle_not_available")
    return puzzle
