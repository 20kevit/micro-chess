"""Recommendation routes: thin handlers delegating to the P7 engine.

``GET /me/recommendations`` is authenticated, deterministic, and
read-only: it recomputes the recommendation from authoritative state on
every call and persists nothing (same precedent as skill_state /
mastery / analytics). Only the machine-readable ``reason`` is exposed;
the internal ``trace`` dict stays server-side and is never serialized.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.modules.recommendations import schemas, service
from app.modules.users.models import User
from app.core.deps import get_db

router = APIRouter(prefix="/me", tags=["recommendations"])


@router.get("/recommendations", response_model=schemas.RecommendationOut | None)
def get_recommendation(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    got = service.recommend_for_user(db, user.id)
    if got is None:
        return None
    return schemas.RecommendationOut(
        exercise_slug=got.exercise_slug,
        puzzle_id=got.puzzle_id,
        reason=got.reason,
        assignment_id=got.assignment_id,
    )
