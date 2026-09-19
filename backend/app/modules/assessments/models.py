"""Assessment session persistence (P6).

One ``assessments`` row is one evaluation session for one student:
who is assessed (``student_user_id``), who opened it
(``created_by_user_id``: an authorized coach or the student), which
direct assignment it optionally executes (``assignment_id``), and its
lifecycle state.

Lifecycle is exactly ``active -> completed | cancelled``. There is no
draft state (a created session is immediately open for attempts) and
terminal states never reopen, mirroring the assignment foundation.
Completing/cancelling only flips this row; attempts, ratings, XP,
evidence, and skill state are never touched.

Only portable SQLAlchemy column types are used (SQLite dev + future
PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Canonical lifecycle states. Created sessions start ``active``; closing
# moves to exactly one terminal state (never back).
ASSESSMENT_ACTIVE = "active"
ASSESSMENT_COMPLETED = "completed"
ASSESSMENT_CANCELLED = "cancelled"
ASSESSMENT_STATUSES = (ASSESSMENT_ACTIVE, ASSESSMENT_COMPLETED, ASSESSMENT_CANCELLED)


class Assessment(Base):
    """One evaluation session for one student.

    ``assignment_id`` is optional context: when the session executes a
    direct coach assignment it points at it (same student, still
    ``assigned`` at creation). Attempts of the session point back via
    ``attempts.assessment_id``; this row never duplicates attempt data.
    """

    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','completed','cancelled')",
            name="ck_assessments_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    # Optional direct-assignment context (stable row reference; the
    # assignment lifecycle itself is owned by relationships).
    assignment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assignments.id"), nullable=True, index=True
    )
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(
        String(20), default=ASSESSMENT_ACTIVE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
