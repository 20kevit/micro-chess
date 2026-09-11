"""Notification application service (Phase 11).

Pipeline (domain code emits an event; this service decides, persists,
and delivers):

```text
emit_event(db, user_id, type, title, body, dedup_key?)
  -> validate type/channel vocabulary
  -> preference decision (mandatory categories always pass; missing
     preference rows default to enabled)
  -> persist notification (UNIQUE dedup_key collapses repeats)
  -> deliver through the channel provider (failures mark the delivery
     row failed; the business operation that emitted the event is never
     affected)
```

Callers must treat emission as best-effort: wrap in try/except so a
notification failure can never fail the underlying business operation.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.notifications import providers
from app.modules.notifications.models import (
    CATEGORIES,
    CATEGORY_ACCOUNT,
    CHANNELS,
    CHANNEL_IN_APP,
    DELIVERY_DELIVERED,
    DELIVERY_FAILED,
    DELIVERY_PENDING,
    DELIVERY_SENT,
    DELIVERY_STATUSES,
    EVENT_TYPES,
    MANDATORY_CATEGORIES,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    category_for_type,
)

logger = logging.getLogger("microchess.notifications")

MAX_TITLE_LEN = 200
MAX_BODY_LEN = 1000


def _clean(text: str | None, limit: int) -> str:
    return (text or "").strip()[:limit]


def is_enabled(db: Session, *, user_id: int, category: str, channel: str = CHANNEL_IN_APP) -> bool:
    """Server-side preference evaluation. Missing rows default to
    enabled; mandatory categories are always enabled."""
    if category in MANDATORY_CATEGORIES:
        return True
    row = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.category == category,
            NotificationPreference.channel == channel,
        )
        .first()
    )
    return bool(row.enabled) if row is not None else True


def _deliver(db: Session, notification: Notification, *, channel: str) -> NotificationDelivery:
    """Create (or reuse) the delivery row and run it through the channel
    provider. Provider failures mark the row failed with a short error
    summary; payloads never reach logs. Idempotent per
    (notification, channel)."""
    existing = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.notification_id == notification.id,
            NotificationDelivery.channel == channel,
        )
        .first()
    )
    if existing is not None and existing.status in (DELIVERY_SENT, DELIVERY_DELIVERED):
        return existing
    delivery = existing
    if delivery is None:
        delivery = NotificationDelivery(
            notification_id=notification.id, channel=channel, status=DELIVERY_PENDING
        )
        db.add(delivery)
        db.flush()
    provider = providers.get_provider(channel)
    if provider is None:
        delivery.status = DELIVERY_FAILED
        delivery.last_error = "unknown_channel"
        db.commit()
        return delivery
    delivery.attempts = (delivery.attempts or 0) + 1
    try:
        outcome = provider.send(notification)
    except Exception:  # noqa: BLE001 - a provider must never break delivery
        logger.exception("notification provider failed (channel=%s)", channel)
        outcome = providers.DeliveryOutcome(delivered=False, error="provider_error")
    if outcome.delivered:
        # In-app presentation is immediate; external channels report sent
        # and confirm delivery later.
        delivery.status = DELIVERY_DELIVERED if channel == CHANNEL_IN_APP else DELIVERY_SENT
        delivery.last_error = ""
    else:
        delivery.status = DELIVERY_FAILED
        delivery.last_error = (outcome.error or "delivery_failed")[:500]
    db.commit()
    db.refresh(delivery)
    return delivery


def emit_event(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    body: str = "",
    channel: str = CHANNEL_IN_APP,
    dedup_key: str | None = None,
) -> Notification | None:
    """Decide, persist, and deliver one platform event.

    Returns the notification, or None when the user's preferences
    suppress this non-critical event. Raises ValueError on unknown
    type/channel vocabulary.
    """
    if type not in EVENT_TYPES:
        raise ValueError("unknown_event_type")
    if channel not in CHANNELS:
        raise ValueError("unknown_channel")
    category = category_for_type(type)
    if category not in CATEGORIES:
        raise ValueError("unknown_event_type")
    if not is_enabled(db, user_id=user_id, category=category, channel=channel):
        return None
    notification = Notification(
        user_id=user_id,
        type=type,
        category=category,
        title=_clean(title, MAX_TITLE_LEN),
        body=_clean(body, MAX_BODY_LEN),
        dedup_key=(dedup_key.strip()[:150] if dedup_key else None) or None,
    )
    db.add(notification)
    try:
        db.commit()
    except IntegrityError:
        # Duplicate event (same dedup_key): collapse to the existing row.
        db.rollback()
        existing = (
            db.query(Notification)
            .filter(Notification.dedup_key == notification.dedup_key)
            .first()
        )
        return existing
    db.refresh(notification)
    _deliver(db, notification, channel=channel)
    return notification


def retry_delivery(db: Session, *, delivery_id: int) -> NotificationDelivery:
    """Retry one failed delivery through its channel provider. Terminal
    (sent/delivered) rows are returned unchanged; only failed rows move
    back through pending. Retries update the same row (no duplicates)."""
    delivery = db.get(NotificationDelivery, delivery_id)
    if delivery is None:
        raise ValueError("delivery_not_found")
    if delivery.status in (DELIVERY_SENT, DELIVERY_DELIVERED):
        return delivery
    if delivery.status not in DELIVERY_STATUSES:
        raise ValueError("invalid_delivery_status")
    notification = db.get(Notification, delivery.notification_id)
    if notification is None:
        raise ValueError("notification_not_found")
    delivery.status = DELIVERY_PENDING
    db.commit()
    db.refresh(delivery)
    return _deliver(db, notification, channel=delivery.channel)


def list_notifications(
    db: Session, *, user_id: int, unread_only: bool = False, page: int = 1, page_size: int = 50
) -> tuple[list[Notification], int]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    total = query.count()
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def unread_count(db: Session, *, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .count()
    )


def mark_read(db: Session, *, user_id: int, notification_id: int) -> Notification:
    """Owner-only read marking. Foreign ids read as not-found (no
    existence leak). Idempotent: repeats return the row unchanged."""
    from datetime import datetime, timezone

    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise ValueError("notification_not_found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(notification)
    return notification


def get_preferences(db: Session, *, user_id: int) -> list[dict]:
    """Full preference matrix with effective state (missing rows read as
    enabled; mandatory categories flagged so clients never offer to
    disable them)."""
    stored = {
        (row.category, row.channel): bool(row.enabled)
        for row in db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == user_id)
        .all()
    }
    matrix = []
    for category in CATEGORIES:
        for channel in CHANNELS:
            matrix.append(
                {
                    "category": category,
                    "channel": channel,
                    "enabled": stored.get((category, channel), True),
                    "mandatory": category in MANDATORY_CATEGORIES,
                }
            )
    return matrix


def set_preference(
    db: Session, *, user_id: int, category: str, channel: str, enabled: bool
) -> dict:
    """Persist one preference. Mandatory categories can never be
    disabled; unknown vocabulary is rejected."""
    from datetime import datetime, timezone

    if category not in CATEGORIES:
        raise ValueError("unknown_category")
    if channel not in CHANNELS:
        raise ValueError("unknown_channel")
    if category in MANDATORY_CATEGORIES and not enabled:
        raise ValueError("mandatory_notification")
    row = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.category == category,
            NotificationPreference.channel == channel,
        )
        .first()
    )
    if row is None:
        row = NotificationPreference(
            user_id=user_id, category=category, channel=channel, enabled=bool(enabled)
        )
        db.add(row)
    else:
        row.enabled = bool(enabled)
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return {
        "category": row.category,
        "channel": row.channel,
        "enabled": bool(row.enabled),
        "mandatory": row.category in MANDATORY_CATEGORIES,
    }


def notification_view(row: Notification) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "category": row.category,
        "title": row.title,
        "body": row.body,
        "read_at": row.read_at,
        "created_at": row.created_at,
    }


def delivery_view(row: NotificationDelivery) -> dict:
    return {
        "id": row.id,
        "notification_id": row.notification_id,
        "channel": row.channel,
        "status": row.status,
        "attempts": row.attempts,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
