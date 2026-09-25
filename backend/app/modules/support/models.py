"""Support persistence (Phase 11).

A support ticket is owned by exactly one authenticated account
(``user_id``); guest support is not enabled (no product requirement).
Lifecycle is ``open -> answered -> closed`` with an audited reopen path
back to ``open``:

* ``open``: created, awaiting staff (owner replies keep it open).
* ``answered``: staff responded, awaiting the owner (owner replies move
  it back to open; staff replies keep it answered).
* ``closed``: messages and re-closing are rejected until an authorized
  staff member explicitly reopens the ticket.

Messages are append-only facts (owner follow-ups + staff responses).
The first owner message is stored at creation time from the ticket's
initial ``message``. ``assigned_admin_id`` records the first staff
member who responded or closed (staff attribution without leaking
unrelated admin data to owners: owner views see only a staff/user flag).

Only portable SQLAlchemy column types are used (SQLite dev + future
PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Canonical support lifecycle states.
STATUS_OPEN = "open"
STATUS_ANSWERED = "answered"
STATUS_CLOSED = "closed"
STATUSES = (STATUS_OPEN, STATUS_ANSWERED, STATUS_CLOSED)

# Bounded input limits (server-enforced; see service + schemas).
MAX_SUBJECT_LEN = 200
MAX_CATEGORY_LEN = 50
MAX_MESSAGE_LEN = 2000


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open','answered','closed')", name="ck_support_tickets_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(MAX_SUBJECT_LEN), default="")
    # Optional free-form category (no invented taxonomy; bounded length).
    category: Mapped[str] = mapped_column(String(MAX_CATEGORY_LEN), default="")
    status: Mapped[str] = mapped_column(String(20), default=STATUS_OPEN, index=True)
    assigned_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportMessage(Base):
    """One append-only conversation entry (owner or staff author)."""

    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("support_tickets.id"), index=True
    )
    author_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    # Server-derived at write time (capability of the author), so owner
    # views can label staff replies without exposing admin identities.
    author_is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    body: Mapped[str] = mapped_column(String(MAX_MESSAGE_LEN), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
