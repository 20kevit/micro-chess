"""P11 channel persistence: push subscriptions, external channel links,
link tokens, analytics events. Notification rows themselves stay in the
existing notifications module (single notification domain).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_push_owner_endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(500))
    p256dh: Mapped[str] = mapped_column(String(200), default="")
    auth: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChannelLink(Base):
    """Verified external channel address (telegram/bale chat id)."""

    __tablename__ = "channel_links"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", name="uq_channel_link_owner_channel"),
        CheckConstraint("channel IN ('telegram','bale')", name="ck_channel_link_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChannelLinkToken(Base):
    """Short-lived one-time linking token (hash at rest)."""

    __tablename__ = "channel_link_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AnalyticsEvent(Base):
    """Privacy-conscious product events (P11 funnel + retention)."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(60), index=True)
    props: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ReminderLog(Base):
    """One reminder decision per (user, local_date, channel): dedup guard."""

    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", "channel", name="uq_reminder_owner_day_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
