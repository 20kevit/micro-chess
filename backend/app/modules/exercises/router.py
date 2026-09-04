"""Exercise catalog routes (read-only for MVP)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.exercises.models import Exercise
from app.modules.exercises.schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(db: Session = Depends(get_db)):
    rows = db.query(Exercise).filter(Exercise.is_active == True).order_by(Exercise.sort_order).all()  # noqa: E712
    return rows
