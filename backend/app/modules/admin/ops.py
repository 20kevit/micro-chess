"""Admin operations service: derived operational aggregates.

All functions are read-only derivations over authoritative tables
(attempts, users, puzzles, evidence, adaptive_recommendations,
billing_*, support_tickets, audit_logs). No new persistence, no
fabricated metrics, no per-slug branching. Routers stay thin.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.admin.models import AuditLog
from app.modules.adaptive.models import AdaptiveRecommendation
from app.modules.billing.models import (
    BillingAttribution,
    BillingCampaign,
    BillingCoupon,
    BillingCouponRedemption,
    BillingPayment,
    BillingSubscription,
    BillingSubscriptionEvent,
)
from app.modules.evidence.models import Evidence
from app.modules.exercises.models import Exercise
from app.modules.gamification_engine.models import PlayerGamificationState, PlayerStreak
from app.modules.generators.models import GeneratorRun
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle, PuzzleValidation
from app.modules.support.models import SupportTicket
from app.modules.users.models import User, UserRole


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
    """Prioritized puzzles needing human review."""
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
    candidates = query.order_by(Puzzle.created_at.desc(), Puzzle.id.desc()).all()
    stats = _puzzle_attempt_stats(db)
    puzzle_ids = [puzzle.id for puzzle in candidates]
    latest_validation: dict[int, str] = {}
    if puzzle_ids:
        for puzzle_id, validation_status in (
            db.query(PuzzleValidation.puzzle_id, PuzzleValidation.status)
            .filter(PuzzleValidation.puzzle_id.in_(puzzle_ids))
            .order_by(
                PuzzleValidation.puzzle_id,
                PuzzleValidation.created_at.desc(),
                PuzzleValidation.id.desc(),
            )
            .all()
        ):
            latest_validation.setdefault(int(puzzle_id), validation_status)

    audit_by_puzzle: dict[int, int | None] = {}
    if puzzle_ids:
        target_ids = [str(puzzle_id) for puzzle_id in puzzle_ids]
        for row in (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "puzzles.create",
                AuditLog.target_type == "puzzle",
                AuditLog.target_id.in_(target_ids),
            )
            .order_by(AuditLog.id.asc())
            .all()
        ):
            try:
                audit_by_puzzle[int(row.target_id)] = row.actor_user_id
            except (TypeError, ValueError):
                continue

    generator_by_id: dict[int, GeneratorRun] = {}
    generator_ids = [
        puzzle.generator_run_id for puzzle in candidates if puzzle.generator_run_id
    ]
    if generator_ids:
        generator_by_id = {
            row.id: row
            for row in db.query(GeneratorRun).filter(GeneratorRun.id.in_(generator_ids)).all()
        }

    creator_ids = {
        int(user_id)
        for user_id in (
            list(audit_by_puzzle.values())
            + [run.requested_by_user_id for run in generator_by_id.values()]
        )
        if user_id is not None
    }
    user_by_id: dict[int, tuple[str | None, str | None]] = {}
    if creator_ids:
        user_by_id = {
            int(user_id): (username, display_name)
            for user_id, username, display_name in (
                db.query(User.id, User.username, User.display_name)
                .filter(User.id.in_(creator_ids))
                .all()
            )
        }

    severity_rank = {"high": 0, "medium": 1, "normal": 2}
    status_rank = {"quarantined": 0, "validated": 1, "reviewed": 2, "approved": 3}
    items: list[dict] = []
    for puzzle in candidates:
        stat = stats.get(puzzle.id, {"attempts": 0, "correct": 0, "failure_rate": None})
        attempts = stat["attempts"]
        failure_rate = stat["failure_rate"]
        validation_status = latest_validation.get(puzzle.id)
        reasons: list[str] = []
        severity = "normal"
        if puzzle.status == "quarantined":
            severity = "high"
            reasons.append("quarantined")
        if (
            attempts >= MIN_ATTEMPTS_FOR_SIGNAL
            and failure_rate is not None
            and failure_rate >= HIGH_FAILURE_THRESHOLD
        ):
            severity = "high"
            reasons.append("high_failure_rate")
        if validation_status == "fail":
            severity = "high"
            reasons.append("validation_failed")
        if attempts < MIN_ATTEMPTS_FOR_SIGNAL:
            reasons.append("insufficient_data")
        if puzzle.status in ("validated", "reviewed"):
            reasons.append("awaiting_review")
        if puzzle.status == "approved":
            reasons.append("awaiting_publish")

        run = generator_by_id.get(puzzle.generator_run_id)
        creator_id = None
        if run is not None:
            creator_id = run.requested_by_user_id
        if creator_id is None:
            creator_id = audit_by_puzzle.get(puzzle.id)
        creator = None
        creator_username = None
        creator_display_name = None
        if creator_id is not None:
            creator_username, creator_display_name = user_by_id.get(
                int(creator_id), (None, None)
            )
            creator = {
                "user_id": int(creator_id),
                "username": creator_username or "",
                "display_name": creator_display_name or "",
            }

        items.append(
            {
                "id": puzzle.id,
                "exercise_slug": puzzle.exercise_slug,
                "status": puzzle.status,
                "source": puzzle.source or "manual",
                "difficulty": puzzle.difficulty,
                "initial_rating": puzzle.initial_rating,
                "created_at": puzzle.created_at,
                "attempts": attempts,
                "usage_attempts": attempts,
                "failure_rate": failure_rate,
                "severity": severity,
                "reasons": reasons,
                "rank": status_rank.get(puzzle.status, 9),
                "fen": puzzle.fen,
                "position_json": puzzle.position_json or {},
                "answer_json": puzzle.answer_json or {},
                "prompt_fa": puzzle.prompt_fa or "",
                "explanation": puzzle.explanation or "",
                "source_reference": puzzle.source_reference,
                "generator_run_id": puzzle.generator_run_id,
                "validation_status": validation_status,
                "latest_validation_status": validation_status,
                "creator": creator,
                "creator_user_id": int(creator_id) if creator_id is not None else None,
                "creator_username": creator_username,
                "creator_display_name": creator_display_name,
            }
        )

    def _sort_key(item: dict) -> tuple:
        created_at = item["created_at"]
        if created_at is not None and created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)
        return (
            severity_rank.get(item["severity"], 9),
            status_rank.get(item["status"], 9),
            created_at or datetime.max,
            item["id"],
        )

    items.sort(key=_sort_key)
    start = (page - 1) * page_size
    return items[start:start + page_size], total


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


TIMELINE_LIMIT = 50


def user_profile_full(db: Session, user_id: int) -> dict | None:
    """Read-only 360-degree operator view of one account.

    Reuses the authoritative derivations (skill_state, mastery,
    gamification projections, billing records). Never writes: it calls
    only read getters (no ``ensure_*``/``get_or_create_*``), so merely
    viewing a profile creates no subscription, XP, or streak rows.
    Every timeline timestamp comes from a durable stored row.
    """
    from app.modules.mastery import service as mastery_service
    from app.modules.skill_state import service as skill_state_service
    from app.modules.verification import service as verification_service

    user = db.get(User, user_id)
    if user is None:
        return None
    verification = verification_service.verification_state(db, user)
    roles = (
        db.query(UserRole.role).filter(UserRole.user_id == user.id).order_by(UserRole.role).all()
    )
    attempts_total = (
        db.query(func.count(Attempt.id)).filter(Attempt.user_id == user.id).scalar() or 0
    )
    first_attempt_at, last_active_at = (
        db.query(func.min(Attempt.created_at), func.max(Attempt.created_at))
        .filter(Attempt.user_id == user.id)
        .first()
    )
    by_exercise = (
        db.query(
            Attempt.exercise_slug,
            func.count(Attempt.id),
            func.sum(case((Attempt.result == "correct", 1), else_=0)),
        )
        .filter(Attempt.user_id == user.id)
        .group_by(Attempt.exercise_slug)
        .order_by(func.count(Attempt.id).desc())
        .limit(20)
        .all()
    )
    skill_state = skill_state_service.skill_state_for_user(db, user.id)
    mastery = mastery_service.mastery_for_user(db, user.id)
    xp_row = (
        db.query(PlayerGamificationState)
        .filter(PlayerGamificationState.user_id == user.id)
        .first()
    )
    streak_row = (
        db.query(PlayerStreak).filter(PlayerStreak.user_id == user.id).first()
    )
    subs = (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user.id)
        .order_by(BillingSubscription.id.desc())
        .limit(5)
        .all()
    )
    sub_ids = [s.id for s in subs]
    sub_events = (
        (
            db.query(BillingSubscriptionEvent)
            .filter(BillingSubscriptionEvent.subscription_id.in_(sub_ids))
            .order_by(BillingSubscriptionEvent.created_at.desc())
            .limit(20)
            .all()
        )
        if sub_ids
        else []
    )
    attribution = (
        db.query(BillingAttribution)
        .filter(BillingAttribution.user_id == user.id)
        .first()
    )
    redemptions = (
        db.query(BillingCouponRedemption, BillingCoupon.code)
        .join(BillingCoupon, BillingCoupon.id == BillingCouponRedemption.coupon_id)
        .filter(BillingCouponRedemption.user_id == user.id)
        .order_by(BillingCouponRedemption.id.desc())
        .limit(10)
        .all()
    )
    payments = (
        db.query(BillingPayment)
        .filter(BillingPayment.user_id == user.id)
        .order_by(BillingPayment.id.desc())
        .limit(10)
        .all()
    )
    recommendations = (
        db.query(AdaptiveRecommendation)
        .filter(AdaptiveRecommendation.user_id == user.id)
        .order_by(AdaptiveRecommendation.created_at.desc())
        .limit(10)
        .all()
    )
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
        .limit(10)
        .all()
    )

    def _campaign_slug(campaign_id: int | None) -> str:
        if not campaign_id:
            return ""
        campaign = db.get(BillingCampaign, campaign_id)
        return campaign.slug if campaign else ""

    current_sub = next(
        (s for s in subs if s.status in ("trialing", "active")), None
    )
    timeline: list[dict] = [
        {"kind": "registered", "at": user.created_at, "detail": user.username or "",
         "durable": True}
    ]
    if first_attempt_at is not None:
        timeline.append({"kind": "first_attempt", "at": first_attempt_at,
                         "detail": "", "durable": True})
    for event in sub_events:
        timeline.append(
            {"kind": "subscription", "at": event.created_at,
             "detail": f"{event.from_status or '—'}->{event.to_status} ({event.reason or ''})",
             "durable": True}
        )
    for payment in payments:
        timeline.append(
            {"kind": "payment", "at": payment.created_at,
             "detail": f"{payment.plan_code} {payment.final_amount_minor} {payment.status}",
             "durable": True}
        )
    for redemption, code in redemptions:
        timeline.append(
            {"kind": "coupon", "at": redemption.created_at,
             "detail": f"{code} {redemption.status}", "durable": True}
        )
    for rec in recommendations:
        timeline.append(
            {"kind": "recommendation", "at": rec.created_at,
             "detail": f"{rec.exercise_slug} {rec.status}", "durable": True}
        )
    for ticket in tickets:
        timeline.append(
            {"kind": "support", "at": ticket.created_at,
             "detail": f"#{ticket.id} {ticket.subject} {ticket.status}", "durable": True}
        )
    timeline = sorted(
        [item for item in timeline if item["at"] is not None],
        key=lambda item: item["at"], reverse=True,
    )[:TIMELINE_LIMIT]
    return {
        "overview": {
            "id": user.id,
            "username": user.username or "",
            "display_name": user.display_name,
            "roles": [r for (r,) in roles],
            "is_active": bool(user.is_active),
            "created_at": user.created_at,
            "last_active_at": last_active_at,
            "attempts_total": int(attempts_total),
            "phone_verified": bool(user.phone_verified),
            "verification_channel": verification.get("channel"),
            "phone_masked": verification.get("phone_masked", ""),
            "verification": verification,
        },
        "verification": verification,
        "learning": {
            "attempts_by_exercise": [
                {"exercise_slug": slug, "attempts": int(attempts), "correct": int(correct or 0)}
                for slug, attempts, correct in by_exercise
            ],
            "skills": [
                {"skill": key, "level": level.level, "confidence": level.confidence,
                 "evidence_count": level.evidence_count}
                for key, level in skill_state.skills.items()
                if level.evidence_count > 0
            ],
            "overall_level": skill_state.overall_level,
            "overall_confidence": skill_state.overall_confidence,
            "mastery": [
                {"skill": key, "status": m.status, "confidence": m.confidence,
                 "attempts": m.attempts}
                for key, m in mastery.items()
            ],
            "xp": (
                {"total": xp_row.total_xp, "level": xp_row.level} if xp_row else None
            ),
            "streak": (
                {"current": streak_row.current_streak, "longest": streak_row.longest_streak}
                if streak_row
                else None
            ),
        },
        "commercial": {
            "current_subscription": (
                {"plan_code": current_sub.plan_code, "status": current_sub.status,
                 "source": current_sub.source,
                 "trial_ends_at": current_sub.trial_ends_at,
                 "current_period_end": current_sub.current_period_end,
                 "coupon_code": current_sub.coupon_code}
                if current_sub
                else None
            ),
            "subscriptions": [
                {"id": s.id, "plan_code": s.plan_code, "status": s.status,
                 "source": s.source, "created_at": s.created_at}
                for s in subs
            ],
            "attribution": (
                {"first_source": attribution.first_source,
                 "first_campaign": _campaign_slug(attribution.first_campaign_id),
                 "first_coupon_code": attribution.first_coupon_code,
                 "first_touched_at": attribution.first_touched_at,
                 "last_source": attribution.last_source}
                if attribution
                else None
            ),
            "redemptions": [
                {"code": code, "status": r.status,
                 "discount_granted_minor": r.discount_granted_minor,
                 "trial_days_granted": r.trial_days_granted, "created_at": r.created_at}
                for r, code in redemptions
            ],
            "payments": [
                {"id": p.id, "plan_code": p.plan_code,
                 "final_amount_minor": p.final_amount_minor, "currency": p.currency,
                 "status": p.status, "provider": p.provider, "created_at": p.created_at}
                for p in payments
            ],
        },
        "timeline": timeline,
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


def provider_health(db: Session) -> dict:
    import os

    from app.core.config import settings
    from app.modules.billing.providers import get_provider
    from app.modules.notify import service as notify_service
    from app.modules.notify.models import ChannelLink, PushSubscription

    vapid = notify_service.vapid_health()
    telegram_configured = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    bale_configured = bool(os.environ.get("BALE_BOT_TOKEN"))
    telegram_verification_available = bool(settings.verification_telegram_enabled and telegram_configured)

    def _count(model, *filters) -> int:
        try:
            query = db.query(model)
            for condition in filters:
                query = query.filter(condition)
            return int(query.count() or 0)
        except Exception:
            return 0

    channels = {
        "in_app": {"available": True},
        "web_push": {
            "available": bool(vapid.get("configured")),
            "subscriptions": _count(PushSubscription),
        },
        "telegram": {
            "available": telegram_configured,
            "configured": telegram_configured,
            "linked_users": _count(ChannelLink, ChannelLink.channel == "telegram"),
        },
        "bale": {
            "available": bale_configured,
            "configured": bale_configured,
            "linked_users": _count(ChannelLink, ChannelLink.channel == "bale"),
        },
    }
    payment_provider = get_provider()
    return {
        "vapid": {
            **vapid,
            "available": bool(vapid.get("configured")),
        },
        "telegram": {"configured": telegram_configured, "available": telegram_configured},
        "bale": {"configured": bale_configured, "available": bale_configured},
        "channels": channels,
        "billing": {
            "provider": payment_provider.code,
            "available": payment_provider.code != "none",
        },
        "verification": {
            "telegram_available": telegram_verification_available,
            "bale_available": True,
        },
    }


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
    providers = provider_health(db)
    return {
        "ok": bool(db_ok and schema.get("ok")),
        "database": {"reachable": bool(db_ok)},
        "schema_status": schema,
        "puzzles": {"total": int(puzzles_total), "published": int(puzzles_published)},
        "providers": providers,
        "channels": providers["channels"],
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
    from app.modules.admin import service as admin_service
    from app.modules.billing import service as billing_service

    # Commercial daily movement (last 14 days): 3 bounded row queries
    # bucketed in Python (portable across SQLite/PostgreSQL, no N+1).
    fortnight_ago = now - timedelta(days=14)
    revenue_rows = (
        db.query(BillingPayment.created_at, BillingPayment.final_amount_minor)
        .filter(
            BillingPayment.status == "verified",
            BillingPayment.created_at >= fortnight_ago,
        )
        .all()
    )
    redemption_rows = (
        db.query(BillingCouponRedemption.created_at)
        .filter(BillingCouponRedemption.created_at >= fortnight_ago)
        .all()
    )
    new_sub_rows = (
        db.query(BillingSubscription.created_at)
        .filter(BillingSubscription.created_at >= fortnight_ago)
        .all()
    )
    revenue_by_day: dict[str, int] = {}
    for created_at, amount in revenue_rows:
        if created_at is None:
            continue
        key = created_at.date().isoformat()
        revenue_by_day[key] = revenue_by_day.get(key, 0) + int(amount or 0)
    redemption_by_day: dict[str, int] = {}
    for (created_at,) in redemption_rows:
        if created_at is None:
            continue
        key = created_at.date().isoformat()
        redemption_by_day[key] = redemption_by_day.get(key, 0) + 1
    subs_by_day: dict[str, int] = {}
    for (created_at,) in new_sub_rows:
        if created_at is None:
            continue
        key = created_at.date().isoformat()
        subs_by_day[key] = subs_by_day.get(key, 0) + 1
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
        key = day.isoformat()
        series.append(
            {
                "day": key,
                "registrations": int(regs),
                "attempts": int(atts),
                "revenue_minor": revenue_by_day.get(key, 0),
                "redemptions": redemption_by_day.get(key, 0),
                "new_subscriptions": subs_by_day.get(key, 0),
            }
        )
    attribution = billing_service.campaign_report(db)
    perf = admin_service.exercise_supply_stats(db)["performance"]
    exercise_success = sorted(
        (
            {"exercise_slug": slug, "attempts": stat["attempts"],
             "success_rate": stat["success_rate"]}
            for slug, stat in perf.items()
        ),
        key=lambda row: row["attempts"],
        reverse=True,
    )[:8]
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
        "attribution": attribution,
        "exercise_success": exercise_success,
    }


def journey_overview(db: Session) -> dict:
    """Free/Premium funnel metrics (all real counts; no OTP/phone values exposed)."""
    from app.modules.billing.models import BillingCouponRedemption, BillingSubscription
    from app.modules.daily_quests.models import DailyQuest, DailyQuestDay
    from app.modules.notifications.models import NotificationDelivery
    from app.modules.notify.models import AnalyticsEvent, ChannelLink, PushSubscription
    from app.modules.onboarding.models import OnboardingProfile
    from app.modules.player.models import PlayerExternalIdentity
    from app.modules.quota.models import DailyUsage

    def _c(q):
        try:
            return int(q.scalar() or 0)
        except Exception:
            return 0

    onboarded = _c(db.query(func.count(OnboardingProfile.id)).filter(
        OnboardingProfile.onboarding_completed.is_(True)))
    placement = _c(db.query(func.count(OnboardingProfile.id)).filter(
        OnboardingProfile.placement_completed.is_(True)))
    verified = _c(db.query(func.count(User.id)).filter(User.phone_verified.is_(True)))
    telegram_verified = _c(db.query(func.count(PlayerExternalIdentity.id)).filter(
        PlayerExternalIdentity.provider == "telegram",
        PlayerExternalIdentity.is_verified.is_(True)))
    bale_verified = _c(db.query(func.count(PlayerExternalIdentity.id)).filter(
        PlayerExternalIdentity.provider == "bale",
        PlayerExternalIdentity.is_verified.is_(True)))
    free_users = _c(db.query(func.count(BillingSubscription.id)).filter(
        BillingSubscription.plan_code == "free", BillingSubscription.status == "active"))
    premium_users = _c(db.query(func.count(BillingSubscription.id)).filter(
        BillingSubscription.plan_code == "premium",
        BillingSubscription.status.in_(["trialing", "active", "past_due"])))
    activations = _c(db.query(func.count(BillingSubscription.id)).filter(
        BillingSubscription.plan_code == "premium", BillingSubscription.source == "coupon"))
    redemptions = _c(db.query(func.count(BillingCouponRedemption.id)).filter(
        BillingCouponRedemption.status == "applied"))
    quest_days = _c(db.query(func.count(DailyQuestDay.id)))
    quests_done = _c(db.query(func.count(DailyQuest.id)).filter(
        DailyQuest.status == "completed"))
    quests_total = _c(db.query(func.count(DailyQuest.id)))
    push = _c(db.query(func.count(PushSubscription.id)))
    telegram = _c(db.query(func.count(ChannelLink.id)).filter(ChannelLink.channel == "telegram"))
    bale = _c(db.query(func.count(ChannelLink.id)).filter(ChannelLink.channel == "bale"))
    notif_failed = _c(db.query(func.count(NotificationDelivery.id)).filter(
        NotificationDelivery.status == "failed"))
    users_at_limit = _c(
        db.query(func.count(func.distinct(DailyUsage.user_id))).filter(DailyUsage.count >= 10)
    )
    events = {
        str(t): int(c) for t, c in
        db.query(AnalyticsEvent.type, func.count(AnalyticsEvent.id))
        .group_by(AnalyticsEvent.type).all()
    }
    return {
        "onboarding_completed": onboarded,
        "placement_completed": placement,
        "phones_verified": verified,
        "telegram_verified": telegram_verified,
        "bale_verified": bale_verified,
        "free_users": free_users,
        "premium_users": premium_users,
        "premium_activations": activations,
        "coupon_redemptions": redemptions,
        "users_at_daily_limit": users_at_limit,
        "quest_days": quest_days,
        "quests_completed": quests_done,
        "quests_total": quests_total,
        "quest_completion_rate": (quests_done / quests_total) if quests_total else 0.0,
        "push_subscriptions": push,
        "telegram_links": telegram,
        "bale_links": bale,
        "notification_delivery_failures": notif_failed,
        "events": events,
    }
