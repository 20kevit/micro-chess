"""Attempt schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.rule_engine.base import AttemptMode


class AttemptIn(BaseModel):
    puzzle_id: int
    answer: dict = {}
    mode: AttemptMode = AttemptMode.PRACTICE
    # Client-reported terminal states (timeout/skipped/abandoned) are accepted
    # as-is without validation; anything else goes through the validator.
    client_result: str | None = None


class AttemptOut(BaseModel):
    id: int
    puzzle_id: int
    exercise_slug: str
    mode: str
    result: str
    score: float
    feedback_key: str = ""
    rating_delta: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
