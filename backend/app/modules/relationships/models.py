"""Relationship persistence (Phase 9).

One ``relationships`` table carries both canonical kinds (``coach`` and
``parent``); the ``kind`` discriminator keeps the two semantics distinct
(no generic "trusted user" access: every authorization check filters by
kind). Lifecycle is exactly ``pending -> active -> revoked`` (see
docs/platform/relationships/* and SECURITY.md section 28).

``assignments`` is the minimal coach-assignment foundation: a coach note
binding a stable exercise identity to one authorized student. Assignments
reference history but never rewrite it.

Only portable SQLAlchemy column types are used (SQLite dev + future
PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Canonical relationship kinds. Coach and parent rows share storage but
# never share authorization: service queries always filter by kind.
KIND_COACH = "coach"
KIND_PARENT = "parent"
KINDS = (KIND_COACH, KIND_PARENT)

# Canonical lifecycle states. There is no separate "rejected" state:
# declining a pending invitation revokes it (history preserved).
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUSES = (STATUS_PENDING, STATUS_ACTIVE, STATUS_REVOKED)

# Assignment states (foundation only; no workflow engine).
ASSIGNMENT_ASSIGNED = "assigned"
ASSIGNMENT_COMPLETED = "completed"
ASSIGNMENT_CANCELLED = "cancelled"
ASSIGNMENT_STATUSES = (ASSIGNMENT_ASSIGNED, ASSIGNMENT_COMPLETED, ASSIGNMENT_CANCELLED)

# Assignment origin. P6 issues direct coach assignments only; the column
# exists so direct work stays queryably separate from system
# suggestions (which live in ``adaptive_recommendations`` and are not
# implemented). A future recommender defers to rows carrying the direct
# source -- that override hook is the reason the column exists today.
SOURCE_COACH_DIRECT = "coach_direct"
ASSIGNMENT_SOURCES = (SOURCE_COACH_DIRECT,)


class Relationship(Base):
    """One directed mentor -> student authorization edge.

    ``mentor_user_id`` holds the coach (kind=coach) or parent
    (kind=parent); ``student_user_id`` holds the student. Only
    ``active`` rows authorize related-student reads.
    """

    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("kind IN ('coach','parent')", name="ck_relationships_kind"),
        CheckConstraint(
            "status IN ('pending','active','revoked')", name="ck_relationships_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    mentor_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    student_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING, index=True)
    # The party that created the invitation (must be mentor or student).
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Assignment(Base):
    """Minimal coach assignment: exercise + note + optional deadline.

    Scoped to one student via the authorizing relationship
    (``relationship_id``). Completing/cancelling never touches attempts,
    ratings, XP, or any other historical record.

    P6 additions (no lifecycle change):

    * ``source`` is always ``coach_direct``: every row here is direct
      coach work, never a system suggestion. The server sets it; no
      client input can forge another origin.
    * ``goal`` is the optional training goal the assignment serves
      (``docs/platform/relationships/COACH_STUDENT.md`` section 7
      lists exercise / exercise set / training goal / deadline / note;
      the multi-puzzle ordered pack stays proposed per DEC-P03 and is
      NOT modeled here). ``note`` keeps carrying the coach's free-form
      instructions.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned','completed','cancelled')",
            name="ck_assignments_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    student_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    relationship_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("relationships.id"), index=True
    )
    # Stable exercise identity (slug); never a mutable row reference.
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    # Optional training goal (free text, no thresholds or rules attached).
    goal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Origin discriminator (P6 separation hook; only direct rows exist).
    source: Mapped[str] = mapped_column(String(30), default=SOURCE_COACH_DIRECT)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ASSIGNMENT_ASSIGNED, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
