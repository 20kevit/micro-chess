"""Billing models: data-driven plans/prices, subscriptions, coupons, attribution, payments.

Conventions: portable SQLAlchemy types only (SQLite dev + future
PostgreSQL). Money is stored as integer minor units (rial for IRR) so
no float rounding ever touches financial values. Historical rows carry
their own snapshots (plan code, price, currency, coupon) and are never
rewritten when current plans change.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BillingPlan(Base):
    """A sellable product tier (e.g. ``free``, ``premium``).

    Pricing lives in ``BillingPlanPrice`` versions, never here.
    """

    __tablename__ = "billing_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable machine code (``free`` / ``premium``); referenced by snapshots.
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name_fa: Mapped[str] = mapped_column(String(100), default="")
    description_fa: Mapped[str] = mapped_column(String(500), default="")
    # Billing cadence of the plan itself (``none`` for free).
    billing_interval: Mapped[str] = mapped_column(String(20), default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingPlanPrice(Base):
    """Immutable price version for a plan.

    Prices are never edited in place: a new version row supersedes the
    old one. Subscriptions snapshot the version they were created under.
    """

    __tablename__ = "billing_plan_prices"
    __table_args__ = (UniqueConstraint("plan_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_plans.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Integer minor units (rial for IRR). Placeholder seed values are
    # documented as non-production until configured.
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    billing_interval: Mapped[str] = mapped_column(String(20), default="monthly")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingSubscription(Base):
    """One user's access grant under a plan/price snapshot.

    Lifecycle: pending -> trialing/active -> expired/cancelled (+ past_due
    reserved for the future provider). Cancellation never removes
    already-paid time: the row stays usable until ``current_period_end``.
    History is append-only; state changes emit ``BillingSubscriptionEvent``.
    """

    __tablename__ = "billing_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_plans.id"), index=True)
    price_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_plan_prices.id"), nullable=True
    )
    # pending | trialing | active | expired | cancelled | past_due
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # free_beta | trial | coupon | manual | paid
    source: Mapped[str] = mapped_column(String(30), default="free_beta")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Snapshots frozen at creation: later plan/price edits never rewrite these.
    plan_code: Mapped[str] = mapped_column(String(50), default="")
    price_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_currency: Mapped[str] = mapped_column(String(3), default="IRR")
    price_interval: Mapped[str] = mapped_column(String(20), default="none")
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingSubscriptionEvent(Base):
    """Append-only audit trail of subscription state changes."""

    __tablename__ = "billing_subscription_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_subscriptions.id"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(20), default="")
    to_status: Mapped[str] = mapped_column(String(20), default="")
    reason: Mapped[str] = mapped_column(String(200), default="")
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class BillingCampaign(Base):
    """Marketing source grouping coupons and attribution (where users came from)."""

    __tablename__ = "billing_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable slug, e.g. ``abadeh-chess-group``.
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name_fa: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(50), default="", index=True)
    medium: Mapped[str] = mapped_column(String(50), default="")
    content: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingCoupon(Base):
    """Promotion code. Normalized uppercase, validated fully server-side."""

    __tablename__ = "billing_coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Normalized (stripped + uppercased) code, e.g. ``ABADEH1405``.
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_campaigns.id"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(String(500), default="")
    # percent | fixed | free_trial
    discount_type: Mapped[str] = mapped_column(String(20), default="free_trial")
    # percent: 1-100. fixed: minor units. free_trial: unused (see trial_days).
    discount_value: Mapped[int] = mapped_column(Integer, default=0)
    # Promotional access duration for free_trial coupons (and optionally
    # combined with percent/fixed coupons).
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_per_user: Mapped[int] = mapped_column(Integer, default=1)
    first_time_only: Mapped[bool] = mapped_column(Boolean, default=False)
    min_amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingCouponPlan(Base):
    """Plans a coupon may apply to. Empty = all active plans."""

    __tablename__ = "billing_coupon_plans"
    __table_args__ = (UniqueConstraint("coupon_id", "plan_id"),)

    coupon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_coupons.id"), primary_key=True
    )
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_plans.id"), primary_key=True
    )


class BillingCouponRedemption(Base):
    """Durable per-use coupon record (never a bare counter increment)."""

    __tablename__ = "billing_coupon_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_coupons.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_subscriptions.id"), nullable=True, index=True
    )
    # applied | revoked
    status: Mapped[str] = mapped_column(String(20), default="applied", index=True)
    # Deterministic idempotency key (coupon+user+context); replays hit the
    # same row instead of creating a duplicate.
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    discount_granted_minor: Mapped[int] = mapped_column(Integer, default=0)
    trial_days_granted: Mapped[int] = mapped_column(Integer, default=0)
    plan_code: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class BillingAttribution(Base):
    """First-touch (permanent) + last-touch (informational) marketing attribution.

    One row per user. First-touch fields are write-once: they survive
    registration, login, and later subscriptions. Last-touch fields update
    on subsequent visits.
    """

    __tablename__ = "billing_attributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    first_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_campaigns.id"), nullable=True
    )
    first_coupon_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_coupons.id"), nullable=True
    )
    first_source: Mapped[str] = mapped_column(String(50), default="")
    first_medium: Mapped[str] = mapped_column(String(50), default="")
    first_content: Mapped[str] = mapped_column(String(100), default="")
    first_landing_path: Mapped[str] = mapped_column(String(500), default="")
    first_referrer: Mapped[str] = mapped_column(String(500), default="")
    first_coupon_code: Mapped[str] = mapped_column(String(64), default="")
    first_touched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_campaigns.id"), nullable=True
    )
    last_source: Mapped[str] = mapped_column(String(50), default="")
    last_medium: Mapped[str] = mapped_column(String(50), default="")
    last_content: Mapped[str] = mapped_column(String(100), default="")
    last_landing_path: Mapped[str] = mapped_column(String(500), default="")
    last_coupon_code: Mapped[str] = mapped_column(String(64), default="")
    last_touched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class BillingPayment(Base):
    """Auditable payment/transaction record. No card data, ever.

    Today's provider is ``none`` (no gateway): rows exist to snapshot
    commercial intent (plan/price/discount/final amount) and to give the
    future provider a clean verification target. Paid access activates
    only from a provider-verified record, never from a browser claim.
    """

    __tablename__ = "billing_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("billing_subscriptions.id"), nullable=True, index=True
    )
    # Commercial snapshot frozen at creation.
    plan_code: Mapped[str] = mapped_column(String(50), default="")
    price_amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    final_amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # none | <future provider code>
    provider: Mapped[str] = mapped_column(String(30), default="none", index=True)
    provider_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    # pending | requires_action | verified | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    verification_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
