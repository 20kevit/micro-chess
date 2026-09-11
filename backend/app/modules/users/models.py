"""User account model. Permanent progress requires an account.

Phase 2: the canonical identity is ``username`` (normalized lowercase,
unique). ``email`` is a Phase 1 legacy column kept only so existing
databases upgrade without data loss; it is never required, never used
for login, and never returned by the API.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


CANONICAL_ROLES = ("PLAYER", "COACH", "PARENT", "ADMIN")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Canonical Phase 2 identity: normalized (strip + lower), unique.
    username: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    # Phase 1 legacy: preserved on upgrade, never set for new accounts.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100), default="")
    # ACTIVE (True) vs SUSPENDED (False). Suspended accounts authenticate
    # neither via login nor via an already-issued session.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )


class UserRole(Base):
    """Persisted role assignment. A user may hold several canonical roles."""

    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint("role IN ('PLAYER','COACH','PARENT','ADMIN')", name="ck_user_roles_role"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship("User", back_populates="roles")
