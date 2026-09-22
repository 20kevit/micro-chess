"""Onboarding + placement persistence (P11).

One row per account. Optional external signals stay optional; the
authoritative placement correction always comes from real exercise
performance (ratings/attempts), never from self-report alone.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


EXPERIENCES = ("new", "beginner", "club", "advanced")
PLAY_FREQUENCIES = ("never", "sometimes", "weekly", "daily")
GOALS = ("fun", "improve", "compete", "coach")
INTENSITIES = ("light", "standard", "intensive")


class OnboardingProfile(Base):
    __tablename__ = "onboarding_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    experience: Mapped[str] = mapped_column(String(20), default="")
    play_frequency: Mapped[str] = mapped_column(String(20), default="")
    fide_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lichess_username: Mapped[str] = mapped_column(String(100), default="")
    chesscom_username: Mapped[str] = mapped_column(String(100), default="")
    goal: Mapped[str] = mapped_column(String(20), default="")
    intensity: Mapped[str] = mapped_column(String(20), default="standard")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Tehran")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    placement_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
