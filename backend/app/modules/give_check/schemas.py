"""Giving Check schemas (practice next + speed sessions)."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.progress.schemas import AttemptOut


class SessionStartIn(BaseModel):
    duration_s: int | None = None


class NextPracticeIn(BaseModel):
    # Puzzle ids to avoid (e.g. just shown). Best-effort variety guard.
    exclude_ids: list[int] = []


class SessionOut(BaseModel):
    session_id: str
    exercise_slug: str
    status: str
    duration_s: int
    started_at: datetime
    expires_at: datetime | None = None
    remaining_ms: int
    buffered: int = 0


class SessionSummary(BaseModel):
    session_id: str
    exercise_slug: str
    status: str
    duration_s: int
    started_at: datetime
    expires_at: datetime | None = None
    remaining_ms: int
    buffered: int = 0
    attempted: int
    correct: int
    partial: int
    wrong: int
    score: float


class PrepareIn(BaseModel):
    count: int = 20


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


class ReportEntry(BaseModel):
    attempt_id: int
    puzzle_id: int
    prompt_fa: str = ""
    fen: str | None = None
    result: str
    score: float
    correct: list[str] = []
    missed: list[str] = []
    wrong: list[str] = []
    created_at: datetime


class SessionReport(BaseModel):
    session: SessionSummary
    entries: list[ReportEntry] = []
