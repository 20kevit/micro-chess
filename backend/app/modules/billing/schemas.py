"""Billing schemas (API boundary). No financial logic here; server computes values."""

from datetime import datetime

from pydantic import BaseModel, Field


class PlanPriceOut(BaseModel):
    version: int
    amount_minor: int
    currency: str
    billing_interval: str


class PlanOut(BaseModel):
    code: str
    name_fa: str
    description_fa: str
    billing_interval: str
    is_active: bool
    sort_order: int
    prices: list[PlanPriceOut]


class SubscriptionOut(BaseModel):
    id: int
    plan_code: str
    status: str
    source: str
    trial_ends_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    price_amount_minor: int | None
    price_currency: str
    coupon_code: str | None
    created_at: datetime


class EntitlementsOut(BaseModel):
    plan_code: str
    status: str
    has_paid_access: bool
    features: list[str]


class AttributionTouchIn(BaseModel):
    campaign_slug: str | None = None
    coupon_code: str | None = None
    source: str | None = None
    medium: str | None = None
    content: str | None = None
    landing_path: str | None = None
    referrer: str | None = None


class CouponValidateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    plan_code: str = "premium"


class CouponQuoteOut(BaseModel):
    code: str
    discount_type: str
    plan_code: str
    price_amount_minor: int | None
    currency: str
    discount_minor: int
    trial_days: int
    final_amount_minor: int | None


class CouponRedeemIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    plan_code: str = "premium"
    idempotency_key: str | None = None


class RedemptionOut(BaseModel):
    id: int
    coupon_code: str
    status: str
    discount_granted_minor: int
    trial_days_granted: int
    plan_code: str
    subscription_id: int | None
    already: bool


class PremiumQuoteOut(BaseModel):
    """Invoice preview for premium activation (display only)."""

    plan_code: str
    plan_name_fa: str
    price_amount_minor: int
    currency: str
    discount_minor: int
    final_amount_minor: int
    coupon_code: str | None = None
    gateway_required: bool = False


class PremiumActivateIn(BaseModel):
    coupon_code: str = Field(min_length=1, max_length=64)


class PremiumActivateOut(BaseModel):
    subscription_id: int
    plan_code: str
    status: str
    final_amount_minor: int
    already: bool


class CampaignOut(BaseModel):
    slug: str
    name_fa: str
    source: str
    medium: str
    content: str
    is_active: bool


class CampaignCreateIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    name_fa: str = ""
    source: str = ""
    medium: str = ""
    content: str = ""


class CouponCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    discount_type: str
    discount_value: int = 0
    trial_days: int = 0
    campaign_slug: str | None = None
    description: str = ""
    currency: str = "IRR"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_redemptions: int | None = None
    max_per_user: int = 1
    first_time_only: bool = False
    min_amount_minor: int = 0
    applicable_plan_codes: list[str] = []


class CouponAdminOut(BaseModel):
    id: int
    code: str
    campaign_slug: str | None
    discount_type: str
    discount_value: int
    trial_days: int
    is_active: bool
    valid_from: datetime | None
    valid_until: datetime | None
    max_redemptions: int | None
    max_per_user: int
    total_redemptions: int
    applicable_plan_codes: list[str] = []


class PlanPriceAdminOut(BaseModel):
    id: int
    version: int
    amount_minor: int
    currency: str
    billing_interval: str
    is_active: bool
    effective_from: datetime | None


class PlanAdminOut(BaseModel):
    code: str
    name_fa: str
    description_fa: str
    billing_interval: str
    is_active: bool
    sort_order: int
    prices: list[PlanPriceAdminOut]


class PlanCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name_fa: str
    description_fa: str = ""
    billing_interval: str = "monthly"
    sort_order: int = 0


class PriceCreateIn(BaseModel):
    amount_minor: int = Field(ge=0)
    currency: str = "IRR"
    billing_interval: str = "monthly"


class CampaignReportOut(BaseModel):
    slug: str
    source: str
    medium: str
    registrations: int
    redemptions: int
    trials: int
    paid: int
