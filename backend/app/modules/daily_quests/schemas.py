"""Daily quest schemas (API boundary)."""

from datetime import datetime

from pydantic import BaseModel


class QuestOut(BaseModel):
    id: int
    slot: int
    kind: str
    title: str
    description: str
    exercise_slug: str
    puzzle_id: int | None
    target_count: int
    progress: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    local_date: str


class TodayOut(BaseModel):
    local_date: str
    timezone: str
    completed_count: int
    total: int
    is_complete: bool
    quests: list[QuestOut]
