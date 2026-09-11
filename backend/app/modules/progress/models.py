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
    # Guest-owned attempts reference the server-controlled guest session.
    # At most one of user_id / guest_session_id is set (enforced in service).
    guest_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("guest_sessions.id"), nullable=True, index=True
    )
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    # "rated" | "practice" (see rule_engine.base.AttemptMode).
    mode: Mapped[str] = mapped_column(String(20), default="practice")
    # "correct"|"partial"|"wrong"|"timeout"|"skipped"|"abandoned".
    result: Mapped[str] = mapped_column(String(20), index=True)
    answer_json: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    # Rating snapshot for rated attempts (server-authoritative; Phase 4).
    # Practice/unrated attempts keep all three NULL. For rated attempts
    # ``rating_after = rating_before + rating_delta`` always holds.
    rating_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Client-reported start of the attempt (nullable for old rows).
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Milliseconds between started_at and submission. None when unknown.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hint ids the user consumed, e.g. ["h1"]. Recorded for rating impact later.
    hints_used: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
