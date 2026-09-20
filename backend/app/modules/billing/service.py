"""Billing service: plans, subscriptions, coupons, attribution, payments.

All business logic lives here; routers stay thin. Every commercial value
(price, discount, trial length, access) is computed server-side — the
client never supplies them. Free beta is the default: entitlement
resolution always falls back to a free subscription, so registration and
existing functionality work with ``payment_provider = none``.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.audit import audit_event
from app.modules.billing import entitlements
from app.modules.billing.models import (
    BillingAttribution,
    BillingCampaign,
    BillingCoupon,
    BillingCouponPlan,
    BillingCouponRedemption,
    BillingPayment,
    BillingPlan,
    BillingPlanPrice,
    BillingSubscription,
    BillingSubscriptionEvent,
)
from app.modules.billing.providers import get_provider

FREE_PLAN_CODE = "free"
PREMIUM_PLAN_CODE = "premium"

# No commercial price is decided yet: the premium plan seeds with NO price
# row, so paid checkout stays disabled until an operator configures one.
# The first operator-configured price must use version >= 2 (version 1 is
# reserved and never seeded as real). See docs/PRICING_AND_BILLING.md.
PLACEHOLDER_NOTE = "commercial_price_not_configured"

SUBSCRIPTION_STATUSES = ("pending", "trialing", "active", "expired", "cancelled", "past_due")
DISCOUNT_TYPES = ("percent", "fixed", "free_trial")


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_coupon_code(code: object) -> str:
    return str(code or "").strip().upper()


def normalize_slug(slug: object) -> str:
    return str(slug or "").strip().lower()


# --- plans & prices -----------------------------------------------------------


def ensure_default_plans(db: Session) -> dict[str, BillingPlan]:
    """Idempotent seed: free (+ active zero price) and premium (no price).

    Premium ships without a price row on purpose: inventing a commercial
    price is prohibited, and paid checkout requires a configured price.
    """
    free = db.query(BillingPlan).filter(BillingPlan.code == FREE_PLAN_CODE).first()
    if free is None:
        free = BillingPlan(
            code=FREE_PLAN_CODE,
            name_fa="رایگان",
            description_fa="دسترسی رایگان بتای میکروچس",
            billing_interval="none",
            is_active=True,
            sort_order=0,
        )
        db.add(free)
        db.flush()
    premium = db.query(BillingPlan).filter(BillingPlan.code == PREMIUM_PLAN_CODE).first()
    if premium is None:
        premium = BillingPlan(
            code=PREMIUM_PLAN_CODE,
            name_fa="حرفه‌ای",
            description_fa="دسترسی کامل آموزشی میکروچس",
            billing_interval="monthly",
            is_active=True,
            sort_order=1,
        )
        db.add(premium)
        db.flush()
    free_price = (
        db.query(BillingPlanPrice)
        .filter(BillingPlanPrice.plan_id == free.id, BillingPlanPrice.version == 1)
        .first()
    )
    if free_price is None:
        db.add(
            BillingPlanPrice(
                plan_id=free.id,
                version=1,
                amount_minor=0,
                currency="IRR",
                billing_interval="none",
                is_active=True,
                effective_from=_utcnow_naive(),
            )
        )
    db.commit()
    db.refresh(free)
    db.refresh(premium)
    return {"free": free, "premium": premium}


def get_plan_by_code(db: Session, code: str) -> BillingPlan | None:
    return db.query(BillingPlan).filter(BillingPlan.code == code).first()


def list_public_plans(db: Session) -> list[dict]:
    """Active plans with their active price versions (display only)."""
    ensure_default_plans(db)
    plans = (
        db.query(BillingPlan)
        .filter(BillingPlan.is_active.is_(True))
        .order_by(BillingPlan.sort_order, BillingPlan.id)
        .all()
    )
    out = []
    for plan in plans:
        prices = (
            db.query(BillingPlanPrice)
            .filter(
                BillingPlanPrice.plan_id == plan.id,
                BillingPlanPrice.is_active.is_(True),
            )
            .order_by(BillingPlanPrice.version.desc())
            .all()
        )
        out.append(
            {
                "code": plan.code,
                "name_fa": plan.name_fa,
                "description_fa": plan.description_fa,
                "billing_interval": plan.billing_interval,
                "is_active": plan.is_active,
                "sort_order": plan.sort_order,
                "prices": [
                    {
                        "version": p.version,
                        "amount_minor": p.amount_minor,
                        "currency": p.currency,
                        "billing_interval": p.billing_interval,
                    }
                    for p in prices
                ],
            }
        )
    return out


def get_active_price(db: Session, plan_id: int) -> BillingPlanPrice | None:
    now = _utcnow_naive()
    return (
        db.query(BillingPlanPrice)
        .filter(
            BillingPlanPrice.plan_id == plan_id,
            BillingPlanPrice.is_active.is_(True),
            (BillingPlanPrice.effective_from.is_(None))
            | (BillingPlanPrice.effective_from <= now),
        )
        .order_by(BillingPlanPrice.version.desc())
        .first()
    )


def paid_checkout_enabled(db: Session) -> bool:
    """Whether paid checkout may proceed today.

    Requires a real gateway (never ``none``) AND a configured premium
    price. Both are false in the free beta, so this is closed by default.
    """
    provider = get_provider()
    if provider.code == "none":
        return False
    premium = get_plan_by_code(db, PREMIUM_PLAN_CODE)
    if premium is None or not premium.is_active:
        return False
    return get_active_price(db, premium.id) is not None


def create_plan(
    db: Session, *, code: str, name_fa: str, description_fa: str = "",
    billing_interval: str = "monthly", sort_order: int = 0, actor_id: int | None = None,
) -> BillingPlan:
    code = normalize_slug(code)
    if not code or len(code) > 50:
        raise ValueError("invalid_plan_code")
    if db.query(BillingPlan).filter(BillingPlan.code == code).first():
        raise ValueError("plan_exists")
    if billing_interval not in ("none", "monthly", "yearly", "lifetime"):
        raise ValueError("invalid_interval")
    plan = BillingPlan(
        code=code,
        name_fa=(name_fa or "").strip()[:100] or code,
        description_fa=(description_fa or "").strip()[:500],
        billing_interval=billing_interval,
        is_active=True,
        sort_order=sort_order,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    audit_event(action="billing.plan_created", actor=actor_id, target_type="plan", target_id=plan.id)
    return plan


def create_price_version(
    db: Session, *, plan_code: str, amount_minor: int, currency: str = "IRR",
    billing_interval: str = "monthly", actor_id: int | None = None,
) -> BillingPlanPrice:
    """Append a new immutable price version (never edit in place)."""
    plan = get_plan_by_code(db, normalize_slug(plan_code))
    if plan is None:
        raise ValueError("plan_not_found")
    if not isinstance(amount_minor, int) or amount_minor < 0:
        raise ValueError("invalid_amount")
    currency = str(currency or "IRR").strip().upper()[:3] or "IRR"
    latest = (
        db.query(BillingPlanPrice)
        .filter(BillingPlanPrice.plan_id == plan.id)
        .order_by(BillingPlanPrice.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    price = BillingPlanPrice(
        plan_id=plan.id,
        version=version,
        amount_minor=amount_minor,
        currency=currency,
        billing_interval=billing_interval,
        is_active=True,
        effective_from=_utcnow_naive(),
    )
    db.add(price)
    db.commit()
    db.refresh(price)
    audit_event(
        action="billing.price_created", actor=actor_id,
        target_type="plan_price", target_id=price.id,
        extra={"plan": plan.code, "version": version},
    )
    return price


# --- subscriptions ------------------------------------------------------------


def _transition(
    db: Session, sub: BillingSubscription, to_status: str,
    reason: str, actor_id: int | None = None,
) -> BillingSubscription:
    if to_status not in SUBSCRIPTION_STATUSES:
        raise ValueError("invalid_status")
    from_status = sub.status
    if from_status == to_status:
        return sub
    sub.status = to_status
    sub.updated_at = _utcnow_naive()
    db.add(
        BillingSubscriptionEvent(
            subscription_id=sub.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason[:200],
            actor_user_id=actor_id,
        )
    )
    db.flush()
    audit_event(
        action=f"billing.subscription_{to_status}", actor=actor_id or sub.user_id,
        target_type="subscription", target_id=sub.id,
        extra={"from": from_status, "reason": reason[:200]},
    )
    return sub


def _refresh_expiry(db: Session, sub: BillingSubscription) -> BillingSubscription:
    """Lazily expire time-bound access (no cron needed at this scale)."""
    now = _utcnow_naive()
    if sub.status == "trialing" and sub.trial_ends_at is not None and sub.trial_ends_at <= now:
        _transition(db, sub, "expired", "trial_ended")
        db.commit()
        db.refresh(sub)
    elif sub.status == "active" and sub.current_period_end is not None and sub.current_period_end <= now:
        # Free-beta rows carry no period end and never expire here.
        _transition(db, sub, "expired", "period_ended")
        db.commit()
        db.refresh(sub)
    elif sub.status == "cancelled" and sub.current_period_end is not None and sub.current_period_end <= now:
        _transition(db, sub, "expired", "cancelled_period_ended")
        db.commit()
        db.refresh(sub)
    return sub


def active_subscription_for(db: Session, user_id: int) -> BillingSubscription | None:
    """Newest usable subscription (trialing/active, or cancelled in-period)."""
    now = _utcnow_naive()
    subs = (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user_id)
        .order_by(BillingSubscription.id.desc())
        .all()
    )
    for sub in subs:
        sub = _refresh_expiry(db, sub)
        if sub.status in ("trialing", "active"):
            return sub
        if (
            sub.status == "cancelled"
            and sub.current_period_end is not None
            and sub.current_period_end > now
        ):
            return sub
    # Fall back to the free subscription (beta default), oldest first.
    for sub in sorted(subs, key=lambda s: s.id):
        if sub.plan_code == FREE_PLAN_CODE and sub.status == "active":
            return sub
    return None


def ensure_free_subscription(db: Session, user_id: int) -> BillingSubscription:
    """Guarantee every account holds free access (idempotent)."""
    ensure_default_plans(db)
    existing = active_subscription_for(db, user_id)
    if existing is not None:
        return existing
    free = get_plan_by_code(db, FREE_PLAN_CODE)
    assert free is not None
    price = get_active_price(db, free.id)
    sub = BillingSubscription(
        user_id=user_id,
        plan_id=free.id,
        price_id=price.id if price else None,
        status="active",
        source="free_beta",
        plan_code=free.code,
        price_amount_minor=price.amount_minor if price else 0,
        price_currency=price.currency if price else "IRR",
        price_interval=price.billing_interval if price else "none",
    )
    db.add(sub)
    db.flush()
    db.add(
        BillingSubscriptionEvent(
            subscription_id=sub.id, from_status="", to_status="active",
            reason="free_beta_grant",
        )
    )
    db.commit()
    db.refresh(sub)
    audit_event(action="billing.subscription_active", actor=user_id,
                target_type="subscription", target_id=sub.id,
                extra={"source": "free_beta"})
    return sub


def subscription_access(db: Session, user_id: int) -> dict:
    """Single authoritative entitlement resolution for a user.

    Returns the usable subscription (free ensured), paid-access flag,
    and the exact feature set. Backend-only: routers enforce this.
    """
    sub = ensure_free_subscription(db, user_id)
    paid = (
        sub.plan_code == PREMIUM_PLAN_CODE
        and sub.status in ("trialing", "active", "past_due")
    )
    features = sorted(entitlements.features_for_plan(sub.plan_code, sub.status, paid))
    return {
        "subscription": sub,
        "has_paid_access": paid,
        "features": features,
        "plan_code": sub.plan_code,
        "status": sub.status,
    }


def user_has_had_trial(db: Session, user_id: int) -> bool:
    return (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user_id,
            BillingSubscription.source.in_(["trial", "coupon"]),
            BillingSubscription.status.in_(["trialing", "active", "expired", "cancelled"]),
        )
        .first()
        is not None
    )


def grant_trial(
    db: Session, *, user_id: int, days: int, coupon_code: str | None = None,
    actor_id: int | None = None, reason: str = "coupon_trial",
) -> BillingSubscription:
    """Grant promotional premium access (trialing). One trial per user."""
    if user_has_had_trial(db, user_id):
        raise ValueError("trial_already_used")
    if not isinstance(days, int) or days < 1 or days > 365:
        raise ValueError("invalid_trial_days")
    ensure_default_plans(db)
    premium = get_plan_by_code(db, PREMIUM_PLAN_CODE)
    assert premium is not None
    now = _utcnow_naive()
    sub = BillingSubscription(
        user_id=user_id,
        plan_id=premium.id,
        price_id=None,
        status="trialing",
        source="coupon" if coupon_code else "trial",
        trial_ends_at=now + timedelta(days=days),
        current_period_start=now,
        current_period_end=now + timedelta(days=days),
        plan_code=premium.code,
        price_amount_minor=None,
        price_currency="IRR",
        price_interval=premium.billing_interval,
        coupon_code=normalize_coupon_code(coupon_code) if coupon_code else None,
    )
    db.add(sub)
    db.flush()
    db.add(
        BillingSubscriptionEvent(
            subscription_id=sub.id, from_status="", to_status="trialing",
            reason=reason[:200], actor_user_id=actor_id,
        )
    )
    db.commit()
    db.refresh(sub)
    audit_event(action="billing.trial_granted", actor=actor_id or user_id,
                target_type="subscription", target_id=sub.id,
                extra={"days": days, "coupon": sub.coupon_code})
    return sub


def cancel_subscription(
    db: Session, *, user_id: int, subscription_id: int,
) -> BillingSubscription:
    sub = db.get(BillingSubscription, subscription_id)
    if sub is None or sub.user_id != user_id:
        raise ValueError("subscription_not_found")
    if sub.status in ("expired", "cancelled"):
        raise ValueError("already_ended")
    if sub.plan_code == FREE_PLAN_CODE:
        raise ValueError("free_plan_immutable")
    sub.cancelled_at = _utcnow_naive()
    # Paid time already granted is kept: access runs to period end.
    _transition(db, sub, "cancelled", "user_cancelled", actor_id=user_id)
    db.commit()
    db.refresh(sub)
    return sub


def activate_paid_subscription(
    db: Session, *, payment_id: int, actor_id: int | None = None,
) -> BillingSubscription:
    """Activate paid access ONLY from a server-verified payment record.

    There is intentionally no path that activates from a browser claim:
    callers must pass a ``BillingPayment`` whose status is ``verified``
    (set exclusively by provider webhook verification).
    """
    payment = db.get(BillingPayment, payment_id)
    if payment is None:
        raise ValueError("payment_not_found")
    if payment.status != "verified":
        raise ValueError("payment_not_verified")
    if payment.subscription_id is not None:
        existing = db.get(BillingSubscription, payment.subscription_id)
        if existing is not None and existing.status == "active":
            return existing
    plan = get_plan_by_code(db, payment.plan_code)
    if plan is None:
        raise ValueError("plan_not_found")
    now = _utcnow_naive()
    period_end = now + timedelta(days=30)
    sub = BillingSubscription(
        user_id=payment.user_id,
        plan_id=plan.id,
        price_id=None,
        status="active",
        source="paid",
        current_period_start=now,
        current_period_end=period_end,
        plan_code=plan.code,
        price_amount_minor=payment.price_amount_minor,
        price_currency=payment.currency,
        price_interval=plan.billing_interval,
        coupon_code=payment.coupon_code,
    )
    db.add(sub)
    db.flush()
    db.add(
        BillingSubscriptionEvent(
            subscription_id=sub.id, from_status="", to_status="active",
            reason=f"payment_verified:{payment.id}", actor_user_id=actor_id,
        )
    )
    payment.subscription_id = sub.id
    payment.updated_at = now
    db.commit()
    db.refresh(sub)
    audit_event(action="billing.subscription_active", actor=actor_id or payment.user_id,
                target_type="subscription", target_id=sub.id,
                extra={"source": "paid", "payment": payment.id})
    return sub


# --- campaigns & coupons --------------------------------------------------------


def create_campaign(
    db: Session, *, slug: str, name_fa: str = "", source: str = "",
    medium: str = "", content: str = "", actor_id: int | None = None,
) -> BillingCampaign:
    slug = normalize_slug(slug)
    if not slug or len(slug) > 100:
        raise ValueError("invalid_slug")
    if db.query(BillingCampaign).filter(BillingCampaign.slug == slug).first():
        raise ValueError("campaign_exists")
    campaign = BillingCampaign(
        slug=slug,
        name_fa=(name_fa or "").strip()[:200],
        source=(source or "").strip()[:50],
        medium=(medium or "").strip()[:50],
        content=(content or "").strip()[:100],
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    audit_event(action="billing.campaign_created", actor=actor_id,
                target_type="campaign", target_id=campaign.id)
    return campaign


def get_campaign_by_slug(db: Session, slug: str) -> BillingCampaign | None:
    slug = normalize_slug(slug)
    if not slug:
        return None
    return db.query(BillingCampaign).filter(BillingCampaign.slug == slug).first()


def create_coupon(
    db: Session, *, code: str, discount_type: str, discount_value: int = 0,
    trial_days: int = 0, campaign_slug: str | None = None,
    description: str = "", currency: str = "IRR",
    valid_from: datetime | None = None, valid_until: datetime | None = None,
    max_redemptions: int | None = None, max_per_user: int = 1,
    first_time_only: bool = False, min_amount_minor: int = 0,
    applicable_plan_codes: list[str] | None = None,
    actor_id: int | None = None,
) -> BillingCoupon:
    code = normalize_coupon_code(code)
    if not code or len(code) > 64:
        raise ValueError("invalid_code")
    if discount_type not in DISCOUNT_TYPES:
        raise ValueError("invalid_discount")
    if discount_type == "percent" and not (1 <= discount_value <= 100):
        raise ValueError("invalid_discount")
    if discount_type == "fixed" and (not isinstance(discount_value, int) or discount_value <= 0):
        raise ValueError("invalid_discount")
    if discount_type == "free_trial" and (not isinstance(trial_days, int) or trial_days < 1):
        raise ValueError("invalid_discount")
    if trial_days and (trial_days < 0 or trial_days > 365):
        raise ValueError("invalid_discount")
    if db.query(BillingCoupon).filter(BillingCoupon.code == code).first():
        raise ValueError("coupon_exists")
    campaign_id = None
    if campaign_slug:
        campaign = get_campaign_by_slug(db, campaign_slug)
        if campaign is None:
            raise ValueError("campaign_not_found")
        campaign_id = campaign.id
    coupon = BillingCoupon(
        code=code,
        campaign_id=campaign_id,
        description=(description or "").strip()[:500],
        discount_type=discount_type,
        discount_value=discount_value,
        trial_days=trial_days,
        currency=str(currency or "IRR").strip().upper()[:3] or "IRR",
        valid_from=valid_from,
        valid_until=valid_until,
        max_redemptions=max_redemptions,
        max_per_user=max(1, max_per_user or 1),
        first_time_only=bool(first_time_only),
        min_amount_minor=max(0, min_amount_minor or 0),
    )
    db.add(coupon)
    db.flush()
    for plan_code in applicable_plan_codes or []:
        plan = get_plan_by_code(db, normalize_slug(plan_code))
        if plan is None:
            raise ValueError("plan_not_found")
        db.add(BillingCouponPlan(coupon_id=coupon.id, plan_id=plan.id))
    db.commit()
    db.refresh(coupon)
    audit_event(action="billing.coupon_created", actor=actor_id,
                target_type="coupon", target_id=coupon.id,
                extra={"code": code, "type": discount_type})
    return coupon


def set_coupon_active(
    db: Session, *, coupon_id: int, is_active: bool, actor_id: int | None = None,
) -> BillingCoupon:
    coupon = db.get(BillingCoupon, coupon_id)
    if coupon is None:
        raise ValueError("coupon_not_found")
    coupon.is_active = bool(is_active)
    db.commit()
    db.refresh(coupon)
    audit_event(action="billing.coupon_deactivated" if not is_active else "billing.coupon_created",
                actor=actor_id, target_type="coupon", target_id=coupon.id)
    return coupon


def get_coupon_by_code(db: Session, code: str) -> BillingCoupon | None:
    code = normalize_coupon_code(code)
    if not code:
        return None
    return db.query(BillingCoupon).filter(BillingCoupon.code == code).first()


def _coupon_plan_codes(db: Session, coupon_id: int) -> list[str]:
    rows = db.query(BillingCouponPlan).filter(BillingCouponPlan.coupon_id == coupon_id).all()
    if not rows:
        return []
    plans = db.query(BillingPlan).filter(BillingPlan.id.in_([r.plan_id for r in rows])).all()
    return [p.code for p in plans]


def validate_coupon(
    db: Session, *, code: str, user_id: int, plan_code: str = PREMIUM_PLAN_CODE,
) -> dict:
    """Authoritative server-side coupon check. Never trust client math.

    Returns ``{coupon, discount_minor, trial_days, final_amount_minor, ...}``
    computed from the current active price. Raises ``ValueError`` with a
    machine code (coupon_not_found/inactive/expired/not_yet_valid/
    max_redemptions_exhausted/per_user_limit/trial_already_used/
    wrong_plan/min_amount_not_met/first_time_only/plan_price_unavailable).
    """
    coupon = get_coupon_by_code(db, code)
    if coupon is None:
        audit_event(action="billing.coupon_rejected", actor=user_id,
                    extra={"code": normalize_coupon_code(code), "reason": "not_found"})
        raise ValueError("coupon_not_found")
    now = _utcnow_naive()
    if not coupon.is_active:
        raise ValueError("coupon_inactive")
    if coupon.valid_from is not None and now < coupon.valid_from:
        raise ValueError("coupon_not_yet_valid")
    if coupon.valid_until is not None and now > coupon.valid_until:
        raise ValueError("coupon_expired")
    mine = (
        db.query(BillingCouponRedemption)
        .filter(
            BillingCouponRedemption.coupon_id == coupon.id,
            BillingCouponRedemption.user_id == user_id,
            BillingCouponRedemption.status == "applied",
        )
        .count()
    )
    if mine >= coupon.max_per_user:
        raise ValueError("per_user_limit")
    total = (
        db.query(BillingCouponRedemption)
        .filter(
            BillingCouponRedemption.coupon_id == coupon.id,
            BillingCouponRedemption.status == "applied",
        )
        .count()
    )
    if coupon.max_redemptions is not None and total >= coupon.max_redemptions:
        raise ValueError("max_redemptions_exhausted")
    plan = get_plan_by_code(db, normalize_slug(plan_code))
    if plan is None or not plan.is_active:
        raise ValueError("wrong_plan")
    allowed = _coupon_plan_codes(db, coupon.id)
    if allowed and plan.code not in allowed:
        raise ValueError("wrong_plan")
    if coupon.first_time_only and user_has_had_trial(db, user_id):
        raise ValueError("first_time_only")
    if coupon.discount_type == "free_trial" and user_has_had_trial(db, user_id):
        # One promotional trial per user across all trial coupons.
        raise ValueError("trial_already_used")
    price = get_active_price(db, plan.id)
    amount = price.amount_minor if price else None
    discount_minor = 0
    if coupon.discount_type == "percent":
        if amount is None:
            raise ValueError("plan_price_unavailable")
        discount_minor = amount * coupon.discount_value // 100
    elif coupon.discount_type == "fixed":
        if amount is None:
            raise ValueError("plan_price_unavailable")
        discount_minor = min(coupon.discount_value, amount)
    if amount is not None and amount < coupon.min_amount_minor:
        raise ValueError("min_amount_not_met")
    final_amount = (amount - discount_minor) if amount is not None else None
    return {
        "coupon": coupon,
        "plan_code": plan.code,
        "price_amount_minor": amount,
        "currency": price.currency if price else coupon.currency,
        "discount_minor": discount_minor,
        "trial_days": coupon.trial_days,
        "final_amount_minor": final_amount,
    }


def redeem_coupon(
    db: Session, *, user_id: int, code: str,
    plan_code: str = PREMIUM_PLAN_CODE, idempotency_key: str | None = None,
) -> dict:
    """Validate + record redemption + grant entitlement, atomically.

    Idempotent: the same ``idempotency_key`` replays to the existing
    redemption instead of duplicating. ``free_trial`` coupons grant a
    trialing subscription immediately (no gateway needed); percent/fixed
    coupons record a pending subscription + pending payment intent that
    activates only after provider verification.
    """
    code = normalize_coupon_code(code)
    key = (idempotency_key or f"redeem:{code}:{user_id}:{normalize_slug(plan_code)}")[:128]
    existing = (
        db.query(BillingCouponRedemption)
        .filter(BillingCouponRedemption.idempotency_key == key)
        .first()
    )
    if existing is not None:
        return {"redemption": existing, "already": True, "subscription_id": existing.subscription_id}
    quote = validate_coupon(db, code=code, user_id=user_id, plan_code=plan_code)
    coupon = quote["coupon"]
    subscription_id = None
    if coupon.discount_type == "free_trial" or quote["trial_days"]:
        sub = grant_trial(
            db, user_id=user_id, days=quote["trial_days"] or coupon.trial_days or 30,
            coupon_code=code, reason="coupon_redeemed",
        )
        subscription_id = sub.id
    else:
        ensure_default_plans(db)
        plan = get_plan_by_code(db, quote["plan_code"])
        assert plan is not None
        price = get_active_price(db, plan.id)
        sub = BillingSubscription(
            user_id=user_id,
            plan_id=plan.id,
            price_id=price.id if price else None,
            status="pending",
            source="coupon",
            plan_code=plan.code,
            price_amount_minor=quote["price_amount_minor"],
            price_currency=quote["currency"],
            price_interval=plan.billing_interval,
            coupon_code=code,
        )
        db.add(sub)
        db.flush()
        db.add(
            BillingSubscriptionEvent(
                subscription_id=sub.id, from_status="", to_status="pending",
                reason=f"coupon_redeemed:{code}",
            )
        )
        db.flush()
        subscription_id = sub.id
        db.add(
            BillingPayment(
                user_id=user_id,
                subscription_id=sub.id,
                plan_code=plan.code,
                price_amount_minor=quote["price_amount_minor"] or 0,
                discount_minor=quote["discount_minor"],
                final_amount_minor=quote["final_amount_minor"] or 0,
                currency=quote["currency"],
                coupon_code=code,
                provider="none",
                status="pending",
                idempotency_key=f"pay:{key}"[:128],
            )
        )
        db.flush()
    redemption = BillingCouponRedemption(
        coupon_id=coupon.id,
        user_id=user_id,
        subscription_id=subscription_id,
        status="applied",
        idempotency_key=key,
        discount_granted_minor=quote["discount_minor"],
        trial_days_granted=quote["trial_days"],
        plan_code=quote["plan_code"],
    )
    db.add(redemption)
    db.commit()
    db.refresh(redemption)
    record_attribution(
        db, user_id=user_id,
        touch={"coupon_code": code, "campaign_slug": (coupon.campaign.slug if coupon.campaign_id else None)},
        allow_first=False,
    )
    audit_event(action="billing.coupon_redeemed", actor=user_id,
                target_type="coupon", target_id=coupon.id,
                extra={"code": code, "subscription": subscription_id})
    return {"redemption": redemption, "already": False, "subscription_id": subscription_id}


# --- attribution --------------------------------------------------------------


def record_attribution(
    db: Session, *, user_id: int, touch: dict, allow_first: bool = True,
) -> BillingAttribution:
    """Persist campaign touch. First-touch is write-once (never overwritten).

    ``touch`` keys: campaign_slug, coupon_code, source, medium, content,
    landing_path, referrer. Unknown campaign slugs are kept as raw
    source text rather than failing (marketing may pre-print codes before
    the campaign row exists).
    """
    campaign = get_campaign_by_slug(db, touch.get("campaign_slug") or "")
    coupon_code = normalize_coupon_code(touch.get("coupon_code") or "")
    coupon = get_coupon_by_code(db, coupon_code) if coupon_code else None
    # Backfill campaign from the coupon's campaign when the URL carried
    # only a code (group codes like ABADEH1405 imply their campaign).
    if campaign is None and coupon is not None and coupon.campaign_id:
        campaign = db.get(BillingCampaign, coupon.campaign_id)
    source = str(touch.get("source") or (campaign.source if campaign else ""))[:50]
    medium = str(touch.get("medium") or (campaign.medium if campaign else ""))[:50]
    content = str(touch.get("content") or (campaign.content if campaign else ""))[:100]
    landing_path = str(touch.get("landing_path") or "")[:500]
    referrer = str(touch.get("referrer") or "")[:500]
    now = _utcnow_naive()
    row = db.query(BillingAttribution).filter(BillingAttribution.user_id == user_id).first()
    if row is None:
        if not allow_first:
            # Redemption-time touch for a user whose registration predates
            # attribution: create a coupon-only row without fabricating a
            # first-touch marketing claim.
            row = BillingAttribution(user_id=user_id)
            db.add(row)
            db.flush()
        else:
            row = BillingAttribution(
                user_id=user_id,
                first_campaign_id=campaign.id if campaign else None,
                first_coupon_id=coupon.id if coupon else None,
                first_source=source,
                first_medium=medium,
                first_content=content,
                first_landing_path=landing_path,
                first_referrer=referrer,
                first_coupon_code=coupon_code,
                first_touched_at=now,
                last_campaign_id=campaign.id if campaign else None,
                last_source=source,
                last_medium=medium,
                last_content=content,
                last_landing_path=landing_path,
                last_coupon_code=coupon_code,
                last_touched_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            audit_event(action="billing.attribution_recorded", actor=user_id,
                        target_type="attribution", target_id=row.id,
                        extra={"source": source, "coupon": coupon_code})
            return row
    # Last-touch refresh (informational; first-touch stays untouched).
    row.last_campaign_id = campaign.id if campaign else row.last_campaign_id
    if source:
        row.last_source = source
    if medium:
        row.last_medium = medium
    if content:
        row.last_content = content
    if landing_path:
        row.last_landing_path = landing_path
    if coupon_code:
        row.last_coupon_code = coupon_code
    row.last_touched_at = now
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def record_registration_attribution(
    db: Session, *, user_id: int, touch: dict | None, coupon_code: str | None,
) -> None:
    """Best-effort registration hook: attribution + coupon + free access.

    Never raises: registration must succeed even when the coupon is
    invalid (the user still gets the free beta; the rejection is
    audited and visible via coupon validation).
    """
    touch = dict(touch or {})
    if coupon_code and not touch.get("coupon_code"):
        touch["coupon_code"] = coupon_code
    try:
        if any(touch.get(k) for k in ("campaign_slug", "coupon_code", "source", "landing_path")):
            record_attribution(db, user_id=user_id, touch=touch, allow_first=True)
    except Exception:
        db.rollback()
    try:
        ensure_free_subscription(db, user_id)
    except Exception:
        db.rollback()
        return
    if coupon_code:
        try:
            redeem_coupon(db, user_id=user_id, code=coupon_code)
        except Exception:
            db.rollback()
            audit_event(action="billing.coupon_rejected", actor=user_id,
                        extra={"code": normalize_coupon_code(coupon_code),
                               "reason": "registration_redeem_failed"})


def campaign_report(db: Session) -> list[dict]:
    """Answer: which campaign produced registrations / trials / paid users."""
    campaigns = db.query(BillingCampaign).order_by(BillingCampaign.id).all()
    out = []
    for campaign in campaigns:
        registrations = (
            db.query(BillingAttribution)
            .filter(BillingAttribution.first_campaign_id == campaign.id)
            .count()
        )
        coupon_ids = [
            c.id for c in db.query(BillingCoupon).filter(
                BillingCoupon.campaign_id == campaign.id
            ).all()
        ]
        redemptions = (
            db.query(BillingCouponRedemption)
            .filter(BillingCouponRedemption.coupon_id.in_(coupon_ids))
            .count()
            if coupon_ids
            else 0
        )
        user_ids = [
            r[0] for r in db.query(BillingAttribution.user_id)
            .filter(BillingAttribution.first_campaign_id == campaign.id).all()
        ]
        trials = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.user_id.in_(user_ids),
                BillingSubscription.source.in_(["trial", "coupon"]),
            )
            .count()
            if user_ids
            else 0
        )
        paid = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.user_id.in_(user_ids),
                BillingSubscription.source == "paid",
                BillingSubscription.status == "active",
            )
            .count()
            if user_ids
            else 0
        )
        out.append(
            {
                "slug": campaign.slug,
                "source": campaign.source,
                "medium": campaign.medium,
                "registrations": registrations,
                "redemptions": redemptions,
                "trials": trials,
                "paid": paid,
            }
        )
    return out
