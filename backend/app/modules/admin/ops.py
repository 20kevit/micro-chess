"""Admin operations service: derived operational aggregates.

All functions are read-only derivations over authoritative tables
(attempts, users, puzzles, evidence, adaptive_recommendations,
billing_*, support_tickets, audit_logs). No new persistence, no
fabricated metrics, no per-slug branching. Routers stay thin.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.adaptive.models import AdaptiveRecommendation
from app.modules.billing.models import (
    BillingCouponRedemption,
    BillingPayment,
    BillingSubscription,
)
from app.modules.evidence.models import Evidence
from app.modules.exercises.models import Exercise
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.support.models import SupportTicket
from app.modules.users.models import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


REVIEW_STATUSES = ("validated", "reviewed", "quarantined", "approved")
FAILURE_RESULTS = ("wrong", "timeout", "abandoned")
LOW_SUPPLY_THRESHOLD = 5
HIGH_FAILURE_THRESHOLD = 0.7
MIN_ATTEMPTS_FOR_SIGNAL = 5


def _puzzle_attempt_stats(db: Session) -> dict[int, dict]:
    rows = (
        db.query(
            Attempt.puzzle_id,
            func.count(Attempt.id).label("attempts"),
            func.sum(case((Attempt.result == "correct", 1), else_=0)).label("correct"),
        )
        .filter(Attempt.puzzle_id.isnot(None))
        .group_by(Attempt.puzzle_id)
        .all()
    )
    out: dict[int, dict] = {}
    for puzzle_id, attempts, correct in rows:
        attempts = int(attempts or 0)
        correct = int(correct or 0)
        out[int(puzzle_id)] = {
            "attempts": attempts,
            "correct": correct,
            "failure_rate": (attempts - correct) / attempts if attempts else None,
        }
    return out


def review_queue(
    db: Session,
    *,
    exercise: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Prioritized puzzles needing human review.

    Priority: quarantined > validation-failed candidates (validated with
    high failure) > newly validated > reviewed > approved awaiting publish.
    Abnormal performance (high failure with sufficient sample) is flagged
    with reasons; sorting is deterministic (severity, age).
    """
    if status is not None and status not in (
        "draft", "validated", "reviewed", "approved", "published",
        "quarantined", "rejected", "retired",
    ):
        raise ValueError("invalid_status")
    query = db.query(Puzzle)
    if exercise:
        query = query.filter(Puzzle.exercise_slug == exercise)
    if status:
        query = query.filter(Puzzle.status == status)
    else:
        query = query.filter(Puzzle.status.in_(REVIEW_STATUSES))
    total = query.count()
    rows = (
        query.order_by(Puzzle.created_at.desc(), Puzzle.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    stats = _puzzle_attempt_stats(db)
    severity_rank = {"quarantined": 0, "validated": 1, "reviewed": 2, "approved": 3}
    items: list[dict] = []
    for puzzle in rows:
        stat = stats.get(puzzle.id, {"attempts": 0, "correct": 0, "failure_rate": None})
        attempts = stat["attempts"]
        failure_rate = stat["failure_rate"]
        reasons: list[str] = []
        severity = "normal"
        if puzzle.status == "quarantined":
            severity = "high"
            reasons.append("quarantined")
        if attempts >= MIN_ATTEMPTS_FOR_SIGNAL and failure_rate is not None and failure_rate >= HIGH_FAILURE_THRESHOLD:
            severity = "high" if severity != "high" else severity
            if severity != "high":
                severity = "medium"
            reasons.append("high_failure_rate")
        if attempts < MIN_ATTEMPTS_FOR_SIGNAL:
            reasons.append("insufficient_data")
        if puzzle.status in ("validated", "reviewed"):
            reasons.append("awaiting_review")
        if puzzle.status == "approved":
            reasons.append("awaiting_publish")
        items.append(
            {
                "id": puzzle.id,
                "exercise_slug": puzzle.exercise_slug,
                "status": puzzle.status,
                "source": puzzle.source,
                "difficulty": puzzle.difficulty,
                "initial_rating": puzzle.initial_rating,
                "created_at": puzzle.created_at,
                "attempts": attempts,
                "failure_rate": failure_rate,
                "severity": severity,
                "reasons": reasons,
                "rank": severity_rank.get(puzzle.status, 9),
            }
        )
    items.sort(key=lambda item: (item["rank"], item["created_at"] or datetime.min))
    return items, total


def retention(db: Session, *, cohort_days: int = 14, max_offset: int = 30) -> dict:
    """Real cohort retention: D1/D7/D14/D30 over registration cohorts.

    Cohort = users registered on a UTC calendar day within the last
    ``cohort_days`` days. Active at offset N = >=1 authenticated attempt
    on cohort_day + N. Cohorts with <5 users report null (insufficient).
    """
    now = _utcnow()
    start_day = (now - timedelta(days=cohort_days)).date()
    users = (
        db.query(User.id, User.created_at)
        .filter(User.created_at >= datetime(start_day.year, start_day.month, start_day.day))
        .all()
    )
    cohorts: dict[str, list[int]] = {}
    user_cohort: dict[int, str] = {}
    for uid, created in users:
        if created is None:
            continue
        day = created.date().isoformat()
        cohorts.setdefault(day, []).append(int(uid))
        user_cohort[int(uid)] = day
    if not cohorts:
        return {"cohorts": [], "offsets": [1, 7, 14, 30]}
    offsets = [n for n in (1, 7, 14, 30) if n <= max_offset]
    # Attempt days per user (authenticated only).
    attempt_rows = (
        db.query(Attempt.user_id, Attempt.created_at)
        .filter(Attempt.user_id.isnot(None))
        .filter(Attempt.created_at >= datetime(start_day.year, start_day.month, start_day.day))
        .all()
    )
    active_days: dict[int, set[str]] = {}
    for uid, created_at in attempt_rows:
        if uid is None or created_at is None:
            continue
        active_days.setdefault(int(uid), set()).add(created_at.date().isoformat())
    from datetime import date as _date

    result = []
    for day in sorted(cohorts):
        members = cohorts[day]
        base = _date.fromisoformat(day)
        row: dict = {"cohort": day, "size": len(members), "rates": {}}
        if len(members) < 5:
            for n in offsets:
                row["rates"][str(n)] = None
            result.append(row)
            continue
        member_set = set(members)
        _ = member_set
        for n in offsets:
            target = (base + timedelta(days=n)).isoformat()
            active = sum(1 for uid in members if target in active_days.get(uid, set()))
            row["rates"][str(n)] = round(active / len(members), 4)
        result.append(row)
    return {"cohorts": result, "offsets": offsets}


def learning_overview(db: Session, *, days: int = 30) -> dict:
    """Learning aggregates: exercise usage + evidence distribution."""
    since = _utcnow() - timedelta(days=days)
    usage = (
        db.query(
            Attempt.exercise_slug,
            func.count(Attempt.id).label("attempts"),
            func.sum(case((Attempt.result == "correct", 1), else_=0)).label("correct"),
            func.count(func.distinct(Attempt.user_id)).label("users"),
        )
        .filter(Attempt.created_at >= since)
        .group_by(Attempt.exercise_slug)
        .all()
    )
    by_mistake = (
        db.query(Evidence.mistake_core, func.count(Evidence.id))
        .filter(Evidence.observed_at >= since)
        .group_by(Evidence.mistake_core)
        .all()
    )
    by_direction = (
        db.query(Evidence.direction, func.count(Evidence.id))
        .filter(Evidence.observed_at >= since)
        .group_by(Evidence.direction)
        .all()
    )
    by_skill = (
        db.query(Evidence.skill_key, func.count(Evidence.id))
        .filter(Evidence.observed_at >= since)
        .group_by(Evidence.skill_key)
        .order_by(func.count(Evidence.id).desc())
        .limit(20)
        .all()
    )
    return {
        "window_days": days,
        "exercise_usage": [
            {
                "exercise_slug": slug,
                "attempts": int(attempts or 0),
                "correct": int(correct or 0),
                "success_rate": (int(correct or 0) / int(attempts)) if attempts else None,
                "users": int(users or 0),
            }
            for slug, attempts, correct, users in usage
        ],
        "mistake_distribution": [
            {"mistake": mistake or "none", "count": int(count)} for mistake, count in by_mistake
        ],
        "direction_distribution": [
            {"direction": direction or "unknown", "count": int(count)}
            for direction, count in by_direction
        ],
        "top_skills": [
            {"skill_key": skill or "none", "count": int(count)} for skill, count in by_skill
        ],
    }


def recommendation_overview(db: Session, *, days: int = 30) -> dict:
    """Adaptive recommendation funnel aggregates (no behavior change)."""
    since = _utcnow() - timedelta(days=days)
    by_status = (
        db.query(AdaptiveRecommendation.status, func.count(AdaptiveRecommendation.id))
        .filter(AdaptiveRecommendation.created_at >= since)
        .group_by(AdaptiveRecommendation.status)
        .all()
    )
    by_reason = (
        db.query(AdaptiveRecommendation.reason, func.count(AdaptiveRecommendation.id))
        .filter(AdaptiveRecommendation.created_at >= since)
        .group_by(AdaptiveRecommendation.reason)
        .all()
    )
    by_exercise = (
        db.query(AdaptiveRecommendation.exercise_slug, func.count(AdaptiveRecommendation.id))
        .filter(AdaptiveRecommendation.created_at >= since)
        .group_by(AdaptiveRecommendation.exercise_slug)
        .order_by(func.count(AdaptiveRecommendation.id).desc())
        .limit(20)
        .all()
    )
    total = sum(int(c) for _, c in by_status)
    return {
        "window_days": days,
        "total": total,
        "by_status": [{"status": s, "count": int(c)} for s, c in by_status],
        "by_reason": [{"reason": r, "count": int(c)} for r, c in by_reason],
        "by_exercise": [{"exercise_slug": e, "count": int(c)} for e, c in by_exercise],
    }


def sales_overview(db: Session) -> dict:
    """Commercial aggregates from authoritative billing records."""
    sub_rows = (
        db.query(BillingSubscription.status, func.count(BillingSubscription.id))
        .group_by(BillingSubscription.status)
        .all()
    )
    pay_rows = (
        db.query(BillingPayment.status, func.count(BillingPayment.id))
        .group_by(BillingPayment.status)
        .all()
    )
    revenue = (
        db.query(func.coalesce(func.sum(BillingPayment.final_amount_minor), 0))
        .filter(BillingPayment.status == "verified")
        .scalar()
        or 0
    )
    redemptions = db.query(func.count(BillingCouponRedemption.id)).scalar() or 0
    return {
        "subscriptions_by_status": [{"status": s, "count": int(c)} for s, c in sub_rows],
        "payments_by_status": [{"status": s, "count": int(c)} for s, c in pay_rows],
        "revenue_minor": int(revenue),
        "revenue_currency": "IRR",
        "redemptions_total": int(redemptions),
    }


def product_insights(db: Session) -> list[dict]:
    """Deterministic rule-based operational signals (no AI certainty)."""
    insights: list[dict] = []
    # Low puzzle supply per active exercise.
    exercises = db.query(Exercise).filter(Exercise.is_active == True).all()  # noqa: E712
    for exercise in exercises:
        published = (
            db.query(func.count(Puzzle.id))
            .filter(Puzzle.exercise_slug == exercise.slug, Puzzle.status == "published")
            .scalar()
            or 0
        )
        if published < LOW_SUPPLY_THRESHOLD:
            insights.append(
                {
                    "key": f"low_supply:{exercise.slug}",
                    "title": f"Low puzzle supply: {exercise.slug}",
                    "severity": "high" if published == 0 else "medium",
                    "domain": "content",
                    "entity": exercise.slug,
                    "evidence": {"published": int(published), "threshold": LOW_SUPPLY_THRESHOLD},
                    "suggestion": "Run the exercise generator or review drafts.",
                }
            )
    # Pending review queue depth.
    pending = (
        db.query(func.count(Puzzle.id))
        .filter(Puzzle.status.in_(("validated", "reviewed", "approved", "quarantined")))
        .scalar()
        or 0
    )
    if pending > 0:
        insights.append(
            {
                "key": "review_queue_depth",
                "title": "Puzzles awaiting review",
                "severity": "medium" if pending < 20 else "high",
                "domain": "content",
                "entity": "review_queue",
                "evidence": {"pending": int(pending)},
                "suggestion": "Triage the review queue oldest-first.",
            }
        )
    # High failure puzzles.
    stats = _puzzle_attempt_stats(db)
    bad = [
        pid
        for pid, stat in stats.items()
        if stat["attempts"] >= MIN_ATTEMPTS_FOR_SIGNAL
        and stat["failure_rate"] is not None
        and stat["failure_rate"] >= HIGH_FAILURE_THRESHOLD
    ]
    if bad:
        insights.append(
            {
                "key": "high_failure_puzzles",
                "title": "Puzzles with abnormal failure rate",
                "severity": "medium",
                "domain": "quality",
                "entity": "puzzles",
                "evidence": {"count": len(bad), "sample_ids": bad[:10]},
                "suggestion": "Inspect quarantined/high-failure items for bad content.",
            }
        )
    # Payment failures.
    failed_payments = (
        db.query(func.count(BillingPayment.id))
        .filter(BillingPayment.status == "failed")
        .scalar()
        or 0
    )
    if failed_payments:
        insights.append(
            {
                "key": "payment_failures",
                "title": "Failed payments need attention",
                "severity": "medium",
                "domain": "sales",
                "entity": "payments",
                "evidence": {"failed": int(failed_payments)},
                "suggestion": "Check provider status and failure reasons.",
            }
        )
    # Open support load.
    open_tickets = (
        db.query(func.count(SupportTicket.id))
        .filter(SupportTicket.status == "open")
        .scalar()
        or 0
    )
    if open_tickets:
        insights.append(
            {
                "key": "open_support",
                "title": "Open support tickets",
                "severity": "medium" if open_tickets < 10 else "high",
                "domain": "support",
                "entity": "support",
                "evidence": {"open": int(open_tickets)},
                "suggestion": "Respond to oldest open tickets first.",
            }
        )
    return insights


def system_health(db: Session) -> dict:
    """Graceful health snapshot; unavailable metrics report as unknown."""
    try:
        from sqlalchemy import text as _text

        db.execute(_text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    try:
        from app.db.migration import SCHEMA_VERSION, get_schema_version

        engine = db.get_bind()
        stored = get_schema_version(engine)
        schema = {"expected": SCHEMA_VERSION, "stored": stored, "ok": stored == SCHEMA_VERSION}
    except Exception:
        schema = {"expected": None, "stored": None, "ok": False}
    puzzles_total = db.query(func.count(Puzzle.id)).scalar() or 0
    puzzles_published = (
        db.query(func.count(Puzzle.id)).filter(Puzzle.status == "published").scalar() or 0
    )
    return {
        "ok": bool(db_ok and schema.get("ok")),
        "database": {"reachable": bool(db_ok)},
        "schema_status": schema,
        "puzzles": {"total": int(puzzles_total), "published": int(puzzles_published)},
    }


def dashboard_extended(db: Session) -> dict:
    """Operational dashboard: KPIs + comparisons + alerts (all real data)."""
    now = _utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    prev_week_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)

    def _count_since(model, column, since):
        return db.query(func.count(model.id)).filter(column >= since).scalar() or 0

    users_total = db.query(func.count(User.id)).scalar() or 0
    new_today = _count_since(User, User.created_at, day_ago)
    new_week = _count_since(User, User.created_at, week_ago)
    new_month = _count_since(User, User.created_at, month_ago)
    active_today = (
        db.query(func.count(func.distinct(Attempt.user_id)))
        .filter(Attempt.user_id.isnot(None), Attempt.created_at >= day_ago)
        .scalar()
        or 0
    )
    active_week = (
        db.query(func.count(func.distinct(Attempt.user_id)))
        .filter(Attempt.user_id.isnot(None), Attempt.created_at >= week_ago)
        .scalar()
        or 0
    )
    attempts_today = _count_since(Attempt, Attempt.created_at, day_ago)
    attempts_week = _count_since(Attempt, Attempt.created_at, week_ago)
    attempts_prev_week = (
        db.query(func.count(Attempt.id))
        .filter(Attempt.created_at >= prev_week_ago, Attempt.created_at < week_ago)
        .scalar()
        or 0
    )
    sales = sales_overview(db)
    insights = product_insights(db)
    # Registrations over time (last 14 days, UTC calendar buckets).
    series = []
    for back in range(13, -1, -1):
        day = (now - timedelta(days=back)).date()
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        regs = (
            db.query(func.count(User.id))
            .filter(User.created_at >= start, User.created_at < end)
            .scalar()
            or 0
        )
        atts = (
            db.query(func.count(Attempt.id))
            .filter(Attempt.created_at >= start, Attempt.created_at < end)
            .scalar()
            or 0
        )
        series.append({"day": day.isoformat(), "registrations": int(regs), "attempts": int(atts)})
    return {
        "users_total": int(users_total),
        "registrations": {"today": int(new_today), "week": int(new_week), "month": int(new_month)},
        "active": {"today": int(active_today), "week": int(active_week)},
        "attempts": {
            "today": int(attempts_today),
            "week": int(attempts_week),
            "prev_week": int(attempts_prev_week),
        },
        "sales": sales,
        "alerts": len(insights),
        "series": series,
    }
