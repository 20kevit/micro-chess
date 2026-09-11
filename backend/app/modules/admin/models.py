"""Administration models (Phase 6).

Administration operates on entities owned by other domains (users,
exercises, puzzles); the only table owned here is the append-only
``AuditLog`` for sensitive administrative actions. Audit rows are
historical facts: never updated or deleted through normal workflows.

Only portable SQLAlchemy column types are used (SQLite dev + future
PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    # Machine-readable action, e.g. "users.suspend", "puzzles.publish".
    action: Mapped[str] = mapped_column(String(100), index=True)
    # Resource reference, e.g. ("user", 7) or ("puzzle", 12).
    target_type: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[str] = mapped_column(String(100), index=True)
    # Non-sensitive context only. Never passwords, tokens, or secrets.
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(20), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
