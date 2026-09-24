"""Daily exercise quota service (Free 10 / Premium 100 per local day).

The limit is server-enforced at attempt-accept time
(``progress.service.submit_attempt`` calls ``check_and_consume`` after
validation, before the attempt row is written). Only validated
correct/partial/wrong attempts consume quota — terminal client states
(timeout/skipped/abandoned) and rejected submissions never touch it,
preserving existing attempt semantics exactly.

Plan resolution reuses the billing entitlement architecture
(``billing.service.subscription_access``): paid access means the
premium limit, everything else means the free limit. No second
entitlement system exists.

Timezone handling: the user's onboarding timezone (``users.timezone``)
with an ``Asia/Tehran`` fallback. Each usage row records the UTC
window of its local day; a mid-day timezone change lands inside the
already-open window, so it can never mint a fresh quota.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.quota.models import DailyUsage
from app.modules.users.models import User

FREE_DAILY_LIMIT = 10
PREMIUM_DAILY_LIMIT = 100

FALLBACK_TIMEZONE = "Asia/Tehran"

# Results that consume quota: validated exercise outcomes. Terminal
# client-reported states never count (existing attempt semantics).
COUNTED_RESULTS = frozenset({"correct", "partial", "wrong"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def user_timezone(db: Session, user_id: int) -> str:
    user = db.get(User, int(user_id))
    tz = (getattr(user, "timezone", "") or "").strip() if user else ""
    if not tz:
        return FALLBACK_TIMEZONE
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return FALLBACK_TIMEZONE
    return tz


def day_window(tz_name: str, now: datetime | None = None) -> tuple[str, datetime, datetime]:
    """(local_date, window_start_utc, window_end_utc) for one timezone."""
    now_utc = now or _utcnow()
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        zone = ZoneInfo(FALLBACK_TIMEZONE)
        tz_name = FALLBACK_TIMEZONE
    local = now_utc.astimezone(zone)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = midnight.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = (midnight + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    return local.strftime("%Y-%m-%d"), start_utc, end_utc


def effective_limit(db: Session, user_id: int) -> tuple[int, str]:
    """(limit, plan_code) from the authoritative entitlement resolution."""
    from app.modules.billing import service as billing_service

    access = billing_service.subscription_access(db, int(user_id))
    if access["has_paid_access"]:
        return PREMIUM_DAILY_LIMIT, access["plan_code"]
    return FREE_DAILY_LIMIT, access["plan_code"]


def _get_or_create_row(db: Session, user_id: int, local_date: str, tz: str,
                       start_utc: datetime, end_utc: datetime) -> DailyUsage:
    row = (
        db.query(DailyUsage)
        .filter(DailyUsage.user_id == int(user_id), DailyUsage.local_date == local_date)
        .first()
    )
    if row is not None:
        return row
    row = DailyUsage(
        user_id=int(user_id), local_date=local_date, timezone=tz,
        window_start_utc=start_utc, window_end_utc=end_utc, count=0,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent creator won the unique key. Rolling back is safe
        # here: the quota check runs before any other flushed write in
        # the attempt transaction, so only this row is discarded.
        db.rollback()
        row = (
            db.query(DailyUsage)
            .filter(DailyUsage.user_id == int(user_id), DailyUsage.local_date == local_date)
            .first()
        )
        assert row is not None
    return row


def _overlapping_row(db: Session, user_id: int, now_utc: datetime) -> DailyUsage | None:
    """A usage row whose UTC window contains now (timezone-hop guard)."""
    rows = db.query(DailyUsage).filter(DailyUsage.user_id == int(user_id)).all()
    for row in rows:
        if row.window_start_utc <= now_utc < row.window_end_utc and (row.count or 0) > 0:
            return row
    return None


def usage_for(db: Session, user_id: int) -> dict:
    """Current quota state for UX (read-only, never consumes)."""
    tz = user_timezone(db, user_id)
    local_date, _, _ = day_window(tz)
    limit, plan = effective_limit(db, user_id)
    row = (
        db.query(DailyUsage)
        .filter(DailyUsage.user_id == int(user_id), DailyUsage.local_date == local_date)
        .first()
    )
    used = int(row.count) if row else 0
    # A timezone hop must not hide already-consumed quota.
    overlap = _overlapping_row(db, user_id, _utcnow())
    if overlap is not None and overlap.local_date != local_date:
        used = max(used, int(overlap.count or 0))
    remaining = max(0, limit - used)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "plan": plan,
        "local_date": local_date,
        "can_practice": remaining > 0,
        "upgrade_available": plan != "premium",
    }


def check_and_consume(db: Session, user_id: int) -> dict:
    """Consume one quota unit or raise ``daily_quota_exceeded``.

    Called after validation inside the attempt transaction (flushes;
    the caller commits). Concurrent creators collapse onto the unique
    row; the limit decision reads the row this transaction will write.
    """
    from app.modules.notify import service as notify_service

    tz = user_timezone(db, user_id)
    local_date, start_utc, end_utc = day_window(tz)
    limit, plan = effective_limit(db, user_id)
    now_utc = _utcnow()
    row = _get_or_create_row(db, user_id, local_date, tz, start_utc, end_utc)
    overlap = _overlapping_row(db, user_id, now_utc)
    target = overlap if overlap is not None else row
    if target.id != row.id:
        # Lock the overlapping row for Postgres concurrency; SQLite
        # serializes writers by itself (the clause is a no-op there).
        target = (
            db.query(DailyUsage)
            .filter(DailyUsage.id == target.id)
            .with_for_update()
            .first()
        ) or target
    used = int(target.count or 0)
    if used >= limit:
        try:
            notify_service.track(db, user_id=int(user_id), type="daily_limit_reached",
                                 props={"plan": plan, "limit": limit})
        except Exception:
            pass
        raise ValueError("daily_quota_exceeded")
    target.count = used + 1
    db.flush()
    return {"used": used + 1, "limit": limit, "remaining": max(0, limit - used - 1), "plan": plan}
