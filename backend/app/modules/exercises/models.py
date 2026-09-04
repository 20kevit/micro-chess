"""Exercise catalog model. An exercise is a type of activity (not one question)."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Exercise(Base):
    __tablename__ = "exercises"

    # Slug is the stable key used by the validator registry (e.g. "piece-recognition").
    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    title_fa: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(String(1000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
