"""Player rating state and immutable rating history (Phase 4).

``PlayerRating`` is the mutable current state: exactly one row per
(authenticated user, exercise). Guests never hold ratings — guest history
is temporary by design and rated attempts require an account, so there is
intentionally no ``guest_session_id`` column here.

``RatingEvent`` is the append-only history: one row per rated attempt
(enforced by the unique ``attempt_id``). Normal application flows never
update or delete events; corrections belong to a future audited admin
workflow (not Phase 4).

Exercise identity is the exercise slug string (same convention as
``Attempt.exercise_slug``): registry slugs and catalog rows share this
key, and no second exercise entity is introduced for ratings.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PlayerRating(Base):
    __tablename__ = "player_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_slug", name="uq_player_rating_owner_exercise"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Exercise slug (registry/catalog key). Plain string like Attempt:
    # ratings must work for any validated exercise slug without forcing
    # every exercise through a second relational entity.
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    # Current rating. Starts at INITIAL_RATING; see service.py.
    rating: Mapped[float] = mapped_column(Float, default=1200.0)
    # Uncertainty/deviation. Explicit Glicko-compatible state: a future
    # Glicko implementation can use this column without a redesign.
    rating_deviation: Mapped[float] = mapped_column(Float, default=350.0)
    # Server-derived: True until PROVISIONAL_THRESHOLD rated attempts.
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    # Number of rated attempts applied to this rating.
    games_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class RatingEvent(Base):
    __tablename__ = "rating_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    # Exactly one rating event per rated attempt (idempotency boundary).
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attempts.id"), unique=True, index=True
    )
    rating_before: Mapped[float] = mapped_column(Float)
    rating_delta: Mapped[float] = mapped_column(Float)
    rating_after: Mapped[float] = mapped_column(Float)
    rating_deviation_before: Mapped[float] = mapped_column(Float)
    rating_deviation_after: Mapped[float] = mapped_column(Float)
    # What caused the change. Phase 4 only produces "attempt"; other
    # reasons (calibration/migration/manual_adjustment) are reserved for
    # future audited workflows and have no writers yet.
    reason: Mapped[str] = mapped_column(String(30), default="attempt")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
