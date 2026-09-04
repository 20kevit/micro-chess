"""Puzzle model. One concrete question/task within an exercise."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Puzzle(Base):
    __tablename__ = "puzzles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), ForeignKey("exercises.slug"), index=True)
    # FEN/position payload when applicable; nullable for non-board exercises.
    fen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Definitive answer. Immutable once published (enforced in service layer).
    answer_json: Mapped[dict] = mapped_column(JSON, default=dict)
    hint_json: Mapped[dict] = mapped_column(JSON, default=dict)
    initial_rating: Mapped[float] = mapped_column(Float, default=1200.0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
