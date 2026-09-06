"""Heavier Side speed-session model (60-second timed sessions).

One new table only, justified by the Speed Mode feature: individual answers
keep flowing through the standard ``attempts`` table (mode=practice, so
``rating_delta`` stays None per the rating-stub rule); this table stores the
authoritative session clock and aggregates. Portable column types only.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class HeavierSideSpeedSession(Base):
    __tablename__ = "heavier_side_speed_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), default="heavier-side", index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # "preparing" | "active" | "finished" | "expired".
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    duration_s: Mapped[int] = mapped_column(Integer, default=60)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Clock starts on begin (not on open), so preparation time is excluded.
    # None while "preparing".
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    # Puzzle ids issued to this session, in order (answer rows live in attempts).
    puzzle_ids: Mapped[list] = mapped_column(JSON, default=list)
    # Attempt ids submitted in this session, in order.
    attempt_ids: Mapped[list] = mapped_column(JSON, default=list)
    attempted_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
