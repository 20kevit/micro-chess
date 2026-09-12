"""Server-side session state (Phase 2).

``AuthSession`` gives every login a revocable server record: logout,
suspension, or expiry invalidates the bearer token before its natural
JWT expiration. ``GuestSession`` is the temporary server-controlled
guest identity; guest is never a persisted user role.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Random public id carried as the JWT ``sid`` claim.
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # SHA-256 hex of the issued token: binds the bearer string to this row
    # (a guessed/forged sid never matches) without storing a secret.
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    # Active role for this session (Phase 12): exactly one canonical role
    # code, always a member of the user's assigned ``user_roles``. The
    # session never inherits another role automatically; when the active
    # role is no longer assigned, authorization fails closed. Nullable
    # only so pre-Phase-12 rows can exist before the v11 backfill; new
    # sessions always set it via the auth service, and a NULL value
    # authenticates as nothing (fail closed).
    active_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GuestSession(Base):
    __tablename__ = "guest_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    # ACTIVE | MIGRATED | REVOKED. Expiry is derived from expires_at.
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    migrated_to_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    migrated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
