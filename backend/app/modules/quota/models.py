"""Daily exercise quota persistence.

One row per (user, user-local calendar day). The row records the UTC
window it was created for so a mid-day timezone change cannot mint a
fresh quota (the overlapping window keeps counting). Only portable
SQLAlchemy column types are used.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_daily_usage_owner_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Local day identity YYYY-MM-DD in the timezone in effect when the
    # row was created.
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Tehran")
    # UTC window [window_start_utc, window_end_utc) this row covers.
    window_start_utc: Mapped[datetime] = mapped_column(DateTime)
    window_end_utc: Mapped[datetime] = mapped_column(DateTime)
    count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
