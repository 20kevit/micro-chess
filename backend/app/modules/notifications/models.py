"""Notification persistence (Phase 11).

Separation required by ``docs/platform/phases/PHASE_11_SUPPORT_AND_NOTIFICATIONS.md``
section 4:

```text
event -> notification -> delivery
```

* ``Notification`` is what the user should see (owner, category, text,
  read state). One row per decision, never mutated except for ``read_at``.
* ``NotificationDelivery`` is one attempt to send it through one channel.
  Retries update the same row (idempotent); a notification never gains a
  second delivery row for the same channel.
* ``NotificationPreference`` is the user's opt-out for one
  (category, channel) pair. Missing rows mean "enabled" (safe default:
  notify). The ``account`` category is mandatory and can never be
  disabled.

Only portable SQLAlchemy column types are used (SQLite dev + future
PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Notification categories. Only categories the platform actually emits
# exist here: support updates and mandatory account/security notices.
CATEGORY_SUPPORT = "support"
CATEGORY_ACCOUNT = "account"
CATEGORIES = (CATEGORY_SUPPORT, CATEGORY_ACCOUNT)

# Mandatory categories can never be disabled by the user.
MANDATORY_CATEGORIES = frozenset({CATEGORY_ACCOUNT})

# Delivery channels. Only in-app delivery exists today; future channels
# register a provider (see providers.py) without changing domain events.
CHANNEL_IN_APP = "in_app"
CHANNELS = (CHANNEL_IN_APP,)

# Event types emitted by the platform. Category is derived from the type
# prefix (``support.*`` -> support, ``account.*`` -> account).
TYPE_SUPPORT_RESPONSE = "support.response"
TYPE_SUPPORT_CLOSED = "support.closed"
TYPE_ACCOUNT_SUSPENDED = "account.suspended"
TYPE_ACCOUNT_REACTIVATED = "account.reactivated"
EVENT_TYPES = (
    TYPE_SUPPORT_RESPONSE,
    TYPE_SUPPORT_CLOSED,
    TYPE_ACCOUNT_SUSPENDED,
    TYPE_ACCOUNT_REACTIVATED,
)

# Delivery states (provider-independent).
DELIVERY_PENDING = "pending"
DELIVERY_SENT = "sent"
DELIVERY_DELIVERED = "delivered"
DELIVERY_FAILED = "failed"
DELIVERY_STATUSES = (
    DELIVERY_PENDING,
    DELIVERY_SENT,
    DELIVERY_DELIVERED,
    DELIVERY_FAILED,
)


def category_for_type(event_type: str) -> str:
    """Derive the preference category from an event type prefix."""
    return event_type.split(".", 1)[0]


class Notification(Base):
    """One user-visible notification (immutable except ``read_at``)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Event type, e.g. "support.response". Whitelisted in the service.
    type: Mapped[str] = mapped_column(String(50), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(String(1000), default="")
    # Stable idempotency key (e.g. "support-message:12"). NULL rows never
    # collide (SQLite/PostgreSQL treat NULL as distinct in UNIQUE).
    dedup_key: Mapped[str | None] = mapped_column(
        String(150), nullable=True, unique=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class NotificationDelivery(Base):
    """One delivery attempt of a notification through one channel."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "channel", name="uq_delivery_notification_channel"),
        CheckConstraint(
            "status IN ('pending','sent','delivered','failed')",
            name="ck_notification_deliveries_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notifications.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DELIVERY_PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # Provider error summary only. Never notification text or payloads.
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class NotificationPreference(Base):
    """One user's opt-out for a (category, channel) pair."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "channel", name="uq_notification_preference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
