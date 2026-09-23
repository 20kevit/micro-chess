"""Player platform models (Phase 3).

``PlayerProfile`` is the non-authentication player identity attached to a
``User`` account (one row per account). ``PlayerExternalIdentity`` links a
self-reported FIDE / Lichess / Chess.com identity to the profile.

External identities are informational only: they are always separate from
MicroChess exercise ratings, and ``is_verified`` is server-controlled
(clients can never set it — see SECURITY.md section 64).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Canonical external chess providers (see USER_PROFILES.md section 3).
PROVIDERS = ("fide", "lichess", "chess_com", "telegram", "bale")


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # At most one primary profile per account.
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), default="")
    bio: Mapped[str] = mapped_column(String(500), default="")
    # Opaque reference only (no uploads in Phase 3).
    avatar_reference: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class PlayerExternalIdentity(Base):
    __tablename__ = "player_external_identities"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('fide','lichess','chess_com','telegram','bale')",
            name="ck_external_identity_provider",
        ),
        # One identity per provider per player (a player links each provider once).
        UniqueConstraint("user_id", "provider", name="uq_external_identity_owner_provider"),
        # A provider account links to at most one MicroChess account.
        UniqueConstraint("provider", "external_username", name="uq_external_identity_provider_account"),
        # Stable platform ids (Telegram/Bale) are globally unique per
        # provider and are the anti-takeover key (usernames never are).
        UniqueConstraint("provider", "provider_user_id", name="uq_external_identity_provider_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)
    # Normalized (strip + lower) at write time so "Omid" and "omid" collide.
    external_username: Mapped[str] = mapped_column(String(100))
    # Self-reported rating; informational, never a MicroChess rating.
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Stable platform user id for telegram/bale (server-verified via
    # contact sharing; never a username). NULL for self-reported rows.
    provider_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Display name reported by the provider (informational only).
    display_name: Mapped[str] = mapped_column(String(100), default="")
    # Server-controlled verification state (never client-settable).
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
