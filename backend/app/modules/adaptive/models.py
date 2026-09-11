"""Adaptive training models (Phase 10).

The adaptive layer is a selection layer, not a source of truth: ratings,
attempts, XP, achievements, puzzle content, and observed difficulty all
remain authoritative in their own domains. The only rows owned here are
recommendation records — the feedback loop required by
``docs/platform/phases/PHASE_10_ADAPTIVE_TRAINING.md`` section 8
(shown / accepted / completed / skipped / result).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Recommendation lifecycle. ``shown`` is the entry state (a ``next`` call
# issued this recommendation); the learner (or their training flow) moves
# it forward. Terminal states never reopen.
STATUS_SHOWN = "shown"
STATUS_ACCEPTED = "accepted"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"

RECOMMENDATION_STATUSES = (
    STATUS_SHOWN,
    STATUS_ACCEPTED,
    STATUS_COMPLETED,
    STATUS_SKIPPED,
)

# Allowed forward transitions (source -> set of destinations).
RECOMMENDATION_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_SHOWN: frozenset({STATUS_ACCEPTED, STATUS_SKIPPED}),
    STATUS_ACCEPTED: frozenset({STATUS_COMPLETED, STATUS_SKIPPED}),
    STATUS_COMPLETED: frozenset(),
    STATUS_SKIPPED: frozenset(),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AdaptiveRecommendation(Base):
    """One server-issued adaptive recommendation (one row per ``next`` call).

    This records *what the system suggested*, never the training facts
    themselves: correctness, ratings, and XP stay on the attempt row.
    ``result`` optionally mirrors the outcome the learner reported for
    this recommendation (e.g. after completing the suggested puzzle);
    it is informational and never recomputed into ratings.
    """

    __tablename__ = "adaptive_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    # Machine-readable selection reason (see adaptive service REASONS).
    reason: Mapped[str] = mapped_column(String(30), index=True)
    # Learner ability estimate at selection time (exercise rating or default).
    ability_rating: Mapped[float] = mapped_column(Float)
    # Difficulty the policy aimed at (never written back to the puzzle).
    target_rating: Mapped[float] = mapped_column(Float)
    # Explicit seed when the caller asked for reproducible selection.
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_SHOWN, index=True)
    # Optional outcome result (correct/partial/wrong/...), informational only.
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
