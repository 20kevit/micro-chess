"""Puzzle schemas."""

from datetime import datetime

from pydantic import BaseModel


class PuzzleOut(BaseModel):
    id: int
    exercise_slug: str
    fen: str | None = None
    position_json: dict = {}
    # Answer is NOT exposed to clients; only hints/metadata.
    hint_json: dict = {}
    initial_rating: float = 1200.0
    is_published: bool
    is_archived: bool
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


class PuzzleCreateIn(BaseModel):
    exercise_slug: str
    fen: str | None = None
    position_json: dict = {}
    answer_json: dict = {}
    hint_json: dict = {}
    initial_rating: float = 1200.0
