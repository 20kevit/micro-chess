"""Piece Recognition schemas (practice next + speed sessions)."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.progress.schemas import AttemptOut


class SessionStartIn(BaseModel):
    duration_s: int | None = None


class SessionOut(BaseModel):
    session_id: str
    exercise_slug: str
    status: str
    duration_s: int
    started_at: datetime
    expires_at: datetime
    remaining_ms: int


class SessionSummary(BaseModel):
    session_id: str
    exercise_slug: str
    status: str
    duration_s: int
    started_at: datetime
    expires_at: datetime
    remaining_ms: int
    attempted: int
    correct: int
    partial: int
    wrong: int
    score: float


class SessionSubmitIn(BaseModel):
    puzzle_id: int
    answer: dict = {}
    hints_used: list[str] = []
    started_at: datetime | None = None


class SessionSubmitOut(BaseModel):
    attempt: AttemptOut
    feedback_key: str = ""
    detail: dict = {}
    session: SessionSummary
