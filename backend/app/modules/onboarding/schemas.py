"""Onboarding schemas (API boundary)."""

from pydantic import BaseModel, Field


class OnboardingIn(BaseModel):
    experience: str = ""
    play_frequency: str = ""
    fide_rating: int | None = None
    lichess_username: str = ""
    chesscom_username: str = ""
    goal: str = ""
    intensity: str = "standard"
    timezone: str = "Asia/Tehran"


class OnboardingOut(BaseModel):
    experience: str
    play_frequency: str
    fide_rating: int | None
    lichess_username: str
    chesscom_username: str
    goal: str
    intensity: str
    timezone: str
    onboarding_completed: bool
    placement_completed: bool


class PlacementItemOut(BaseModel):
    exercise_slug: str
    puzzle_id: int
    reason: str


class PlanOut(BaseModel):
    onboarding_completed: bool
    placement_completed: bool
    intensity: str
    goal_text: str
    focus_exercise: str | None
    headline: str
    summary: str
