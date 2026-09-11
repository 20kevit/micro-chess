"""Gamification persistence (Phase 5).

``PlayerGamificationState`` is the mutable read-optimized projection:
exactly one row per authenticated user (guests hold no persistent
gamification state — see training/GAMIFICATION.md section 11).

``XpEvent`` is the append-only ledger: one row per XP-earning attempt
(enforced by the unique ``attempt_id``). Normal application flows never
update or delete events; the ledger stays the historical source of
truth and the materialized total must always equal its sum.

``PlayerStreak`` materializes the current/longest learning streak plus
the last qualifying UTC date. It is updated transactionally with the
attempt that extends it; repeated processing of the same attempt or
repeated activity on the same date never double-counts.

``PlayerAchievement`` records one-time unlocks: one row per
(user, achievement_code), enforced by a unique constraint. Definitions
live in ``service.ACHIEVEMENTS`` (code catalog); no admin achievement
management exists in Phase 5.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PlayerGamificationState(Base):
    __tablename__ = "player_gamification_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Exactly one gamification state per authenticated user.
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    # Server-derived from total_xp (see service.level_for_total).
    level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class XpEvent(Base):
    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # XP granted by this event. Always positive in Phase 5.
    amount: Mapped[int] = mapped_column(Integer)
    # What caused the award. Phase 5 only produces "attempt".
    reason: Mapped[str] = mapped_column(String(30), default="attempt")
    # Exactly one XP event per qualifying attempt (idempotency boundary).
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attempts.id"), unique=True, index=True
    )
    # Materialized total immediately after this award (explains the balance).
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PlayerStreak(Base):
    __tablename__ = "player_streaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Exactly one streak row per authenticated user.
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    # UTC date of the most recent qualifying activity (None until the first).
    last_qualified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class PlayerAchievement(Base):
    __tablename__ = "player_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_code", name="uq_player_achievement_owner_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Code from the service catalog (service.ACHIEVEMENTS); no separate
    # definition table in Phase 5 (no admin management yet).
    achievement_code: Mapped[str] = mapped_column(String(50), index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
