"""Recommendation schemas (P8 integration).

Response-only view over the read-only P7 engine. The internal ``trace``
dict never leaves the server; the UI receives a single machine-readable
``reason`` it can translate.
"""

from pydantic import BaseModel


class RecommendationOut(BaseModel):
    exercise_slug: str
    puzzle_id: int
    reason: str
    assignment_id: int | None = None
