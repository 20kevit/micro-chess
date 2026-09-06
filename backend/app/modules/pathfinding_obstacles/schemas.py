"""Pathfinding-with-obstacles schemas: step oracle + practice + speed."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.progress.schemas import AttemptOut


class StepIn(BaseModel):
    puzzle_id: int
    # Current board position (server rebuilds the live enemy state from it;
    # kind/target come from the stored answer, never from the client).
    fen: str
    # Current square of the selected piece.
    selected_at: str = ""
    from_square: str = Field(default="", alias="from")
    to_square: str = Field(default="", alias="to")

    model_config = {"populate_by_name": True}


class StepOut(BaseModel):
    ok: bool
    # Updated position (unchanged input when the step is rejected).
    fen: str
    selected_at: str
    reached: bool
    captured: str | None = None
    message_key: str = ""


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
