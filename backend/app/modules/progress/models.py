"""Attempt model. One user attempt at a puzzle. Stores raw answer for future analytics."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nullable user: allows future anonymous-transfer flow without restructuring.
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    # "rated" | "practice" (see rule_engine.base.AttemptMode).
    mode: Mapped[str] = mapped_column(String(20), default="practice")
    # "correct"|"partial"|"wrong"|"timeout"|"skipped"|"abandoned".
    result: Mapped[str] = mapped_column(String(20), index=True)
    answer_json: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    # Reserved for future rating engine; null until rating is implemented.
    rating_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
