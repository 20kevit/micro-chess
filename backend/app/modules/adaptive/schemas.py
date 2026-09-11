"""Adaptive training schemas (Phase 10). Response-only views over derived
signals plus the owned recommendation/outcome records. Never carries
answers, scores, or other learners' data."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.puzzles.schemas import PuzzleOut


class ExerciseSignalsOut(BaseModel):
    exercise: str
    attempts: int
    accuracy: float
    recent_accuracy: float | None = None
    recent_failures: int
    repeated_mistakes: int
    avg_response_ms: float | None = None
    days_since_last: int | None = None
    rating: float | None = None
    provisional: bool | None = None
    games: int
    rating_trend: float
    reason: str


class AdaptiveOverviewOut(BaseModel):
    exercises: list[ExerciseSignalsOut]
    recommended_exercise: str | None = None
    reason: str | None = None


class AdaptiveNextOut(BaseModel):
    # The selected content (answer never included — see PuzzleOut).
    puzzle: PuzzleOut
    reason: str
    ability_rating: float
    target_rating: float
    observed_difficulty: str
    recommendation_id: int
    fallback: bool = False


class RecommendationOut(BaseModel):
    id: int
    exercise_slug: str
    puzzle_id: int
    reason: str
    ability_rating: float
    target_rating: float
    seed: int | None = None
    status: str
    result: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OutcomeIn(BaseModel):
    status: str = Field(description="accepted | completed | skipped")
    result: str | None = Field(default=None, description="correct | partial | wrong | ...")
