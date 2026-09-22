"""Daily quest persistence (P11).

One ``DailyQuestDay`` per (user, local_date); exactly three
``DailyQuest`` rows per day (slots 1..3, kinds core/review/challenge).
Plans are stable: created once per local day, never regenerated on
refresh. Completion is idempotent and server-authoritative.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


KIND_CORE = "core"
KIND_REVIEW = "review"
KIND_CHALLENGE = "challenge"
KINDS = (KIND_CORE, KIND_REVIEW, KIND_CHALLENGE)

STATUS_PENDING = "pending"
STATUS_STARTED = "started"
STATUS_COMPLETED = "completed"
STATUSES = (STATUS_PENDING, STATUS_STARTED, STATUS_COMPLETED)


class DailyQuestDay(Base):
    __tablename__ = "daily_quest_days"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_quest_day_owner_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Local day identity YYYY-MM-DD in the user's timezone.
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Tehran")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class DailyQuest(Base):
    __tablename__ = "daily_quests"
    __table_args__ = (
        UniqueConstraint("day_id", "slot", name="uq_quest_day_slot"),
        CheckConstraint("slot IN (1,2,3)", name="ck_quest_slot"),
        CheckConstraint(
            "kind IN ('core','review','challenge')", name="ck_quest_kind"
        ),
        CheckConstraint(
            "status IN ('pending','started','completed')", name="ck_quest_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_id: Mapped[int] = mapped_column(Integer, ForeignKey("daily_quest_days.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    puzzle_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("puzzles.id"), nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=5)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reward_granted: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
