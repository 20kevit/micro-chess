"""Exercise catalog routes (read-only for MVP)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.exercises.models import Exercise
from app.modules.exercises.schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(db: Session = Depends(get_db)):
    rows = db.query(Exercise).filter(Exercise.is_active == True).order_by(Exercise.sort_order).all()  # noqa: E712
    return rows


@router.get("/{exercise_slug}", response_model=ExerciseOut)
def get_exercise(exercise_slug: str, db: Session = Depends(get_db)):
    # Player-facing discovery detail: metadata only, never hidden answers
    # or server-only validation data. Inactive exercises stay visible as
    # unavailable (is_active=False) so the UI can show them as coming soon.
    exercise = db.query(Exercise).filter(Exercise.slug == exercise_slug).first()
    if exercise is None:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    return exercise
