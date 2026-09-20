"""Billing routes: thin wiring over the billing service.

Free beta: plan listing is public; quotes/redemption/attribution are
authenticated (per-user limits are meaningless anonymously). Premium
gates are enforced server-side via ``require_entitlement`` — frontend
hiding is UX only. Paid activation has no browser-triggered path.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_current_session_optional, get_current_user_optional, get_db
from app.modules.auth.models import AuthSession
from app.modules.billing import schemas, service
from app.modules.billing.entitlements import ALL_FEATURES
from app.modules.users.models import User

router = APIRouter(tags=["billing"])
admin_router = APIRouter(prefix="/admin/billing", tags=["admin-billing"])

_COUPON_ERRORS = {
    "coupon_not_found": 404,
    "coupon_inactive": 422,
    "coupon_not_yet_valid": 422,
    "coupon_expired": 422,
    "max_redemptions_exhausted": 409,
    "per_user_limit": 409,
    "trial_already_used": 409,
    "wrong_plan": 422,
    "min_amount_not_met": 422,
    "first_time_only": 409,
    "plan_price_unavailable": 409,
}


def require_entitlement(feature: str):
    """Dependency factory enforcing a billing entitlement server-side.

    401 when unauthenticated, 403 (``premium_required``) when the
    session's subscription lacks the feature. Unknown features deny.
    """
    if feature not in ALL_FEATURES:
        raise ValueError("unknown_feature")

    def _check(
        db: Session = Depends(get_db),
        user: User | None = Depends(get_current_user_optional),
        session: AuthSession | None = Depends(get_current_session_optional),
    ) -> User:
        if user is None or session is None:
            raise HTTPException(status_code=401, detail="auth_required")
        access = service.subscription_access(db, user.id)
        if feature not in access["features"]:
            raise HTTPException(status_code=403, detail="premium_required")
        return user

    return _check


def _require_user(
    user: User | None = Depends(get_current_user_optional),
    session: AuthSession | None = Depends(get_current_session_optional),
) -> User:
    if user is None or session is None:
        raise HTTPException(status_code=401, detail="auth_required")
    return user


def _sub_out(sub) -> schemas.SubscriptionOut:
    return schemas.SubscriptionOut(
        id=sub.id,
        plan_code=sub.plan_code,
        status=sub.status,
        source=sub.source,
        trial_ends_at=sub.trial_ends_at,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        price_amount_minor=sub.price_amount_minor,
        price_currency=sub.price_currency,
        coupon_code=sub.coupon_code,
        created_at=sub.created_at,
    )


# --- public -------------------------------------------------------------------


@router.get("/billing/plans", response_model=list[schemas.PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return service.list_public_plans(db)


# --- self ---------------------------------------------------------------------


@router.get("/billing/me/subscription", response_model=schemas.SubscriptionOut)
def my_subscription(db: Session = Depends(get_db), user: User = Depends(_require_user)):
    return _sub_out(service.ensure_free_subscription(db, user.id))


@router.get("/billing/me/entitlements", response_model=schemas.EntitlementsOut)
def my_entitlements(db: Session = Depends(get_db), user: User = Depends(_require_user)):
    access = service.subscription_access(db, user.id)
    return schemas.EntitlementsOut(
        plan_code=access["plan_code"],
        status=access["status"],
        has_paid_access=access["has_paid_access"],
        features=access["features"],
    )


@router.post("/billing/me/attribution", status_code=204)
def touch_attribution(
    body: schemas.AttributionTouchIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_user),
):
    service.record_attribution(db, user_id=user.id, touch=body.model_dump())
    return None


@router.post("/billing/coupons/validate", response_model=schemas.CouponQuoteOut)
def validate_coupon(
    body: schemas.CouponValidateIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_user),
):
    try:
        quote = service.validate_coupon(
            db, code=body.code, user_id=user.id, plan_code=body.plan_code
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=_COUPON_ERRORS.get(str(exc), 400), detail=str(exc)
        )
    coupon = quote["coupon"]
    return schemas.CouponQuoteOut(
        code=coupon.code,
        discount_type=coupon.discount_type,
        plan_code=quote["plan_code"],
        price_amount_minor=quote["price_amount_minor"],
        currency=quote["currency"],
        discount_minor=quote["discount_minor"],
        trial_days=quote["trial_days"],
        final_amount_minor=quote["final_amount_minor"],
    )


@router.post("/billing/coupons/redeem", response_model=schemas.RedemptionOut)
def redeem_coupon(
    body: schemas.CouponRedeemIn,
    db: Session = Depends(get_db),
    user: User = Depends(_require_user),
):
    try:
        outcome = service.redeem_coupon(
            db, user_id=user.id, code=body.code,
            plan_code=body.plan_code, idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=_COUPON_ERRORS.get(str(exc), 400), detail=str(exc)
        )
    redemption = outcome["redemption"]
    coupon = db.get(service.BillingCoupon, redemption.coupon_id)
    return schemas.RedemptionOut(
        id=redemption.id,
        coupon_code=coupon.code if coupon else "",
        status=redemption.status,
        discount_granted_minor=redemption.discount_granted_minor,
        trial_days_granted=redemption.trial_days_granted,
        plan_code=redemption.plan_code,
        subscription_id=redemption.subscription_id,
        already=outcome["already"],
    )


@router.post("/billing/me/subscription/cancel", response_model=schemas.SubscriptionOut)
def cancel_my_subscription(
    db: Session = Depends(get_db), user: User = Depends(_require_user)
):
    current = service.active_subscription_for(db, user.id)
    if current is None:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    try:
        sub = service.cancel_subscription(
            db, user_id=user.id, subscription_id=current.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _sub_out(sub)


@router.get("/billing/me/advanced-overview")
def advanced_overview(user: User = Depends(require_entitlement("advanced_analytics"))):
    """Premium-gated example: server-enforced advanced analytics surface.

    Free-beta endpoints are untouched; this new surface proves backend
    entitlement enforcement (free sessions get 403 ``premium_required``).
    """
    return {"ok": True, "user_id": user.id, "surface": "advanced_analytics"}


# --- admin --------------------------------------------------------------------


def _coupon_admin_view(db: Session, coupon) -> schemas.CouponAdminOut:
    total = (
        db.query(service.BillingCouponRedemption)
        .filter(
            service.BillingCouponRedemption.coupon_id == coupon.id,
            service.BillingCouponRedemption.status == "applied",
        )
        .count()
    )
    campaign = db.get(service.BillingCampaign, coupon.campaign_id) if coupon.campaign_id else None
    return schemas.CouponAdminOut(
        id=coupon.id,
        code=coupon.code,
        campaign_slug=campaign.slug if campaign else None,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        trial_days=coupon.trial_days,
        is_active=coupon.is_active,
        valid_from=coupon.valid_from,
        valid_until=coupon.valid_until,
        max_redemptions=coupon.max_redemptions,
        max_per_user=coupon.max_per_user,
        total_redemptions=total,
    )


@admin_router.get("/campaigns", response_model=list[schemas.CampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    rows = db.query(service.BillingCampaign).order_by(service.BillingCampaign.id).all()
    return [
        schemas.CampaignOut(
            slug=r.slug, name_fa=r.name_fa, source=r.source,
            medium=r.medium, content=r.content, is_active=r.is_active,
        )
        for r in rows
    ]


@admin_router.post("/campaigns", response_model=schemas.CampaignOut, status_code=201)
def create_campaign(
    body: schemas.CampaignCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_MANAGE)),
):
    try:
        campaign = service.create_campaign(
            db, slug=body.slug, name_fa=body.name_fa, source=body.source,
            medium=body.medium, content=body.content, actor_id=user.id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(status_code=409 if code == "campaign_exists" else 422, detail=code)
    return schemas.CampaignOut(
        slug=campaign.slug, name_fa=campaign.name_fa, source=campaign.source,
        medium=campaign.medium, content=campaign.content, is_active=campaign.is_active,
    )


@admin_router.get("/coupons", response_model=list[schemas.CouponAdminOut])
def list_coupons(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    rows = db.query(service.BillingCoupon).order_by(service.BillingCoupon.id).all()
    return [_coupon_admin_view(db, row) for row in rows]


@admin_router.post("/coupons", response_model=schemas.CouponAdminOut, status_code=201)
def create_coupon(
    body: schemas.CouponCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_MANAGE)),
):
    try:
        coupon = service.create_coupon(
            db, code=body.code, discount_type=body.discount_type,
            discount_value=body.discount_value, trial_days=body.trial_days,
            campaign_slug=body.campaign_slug, description=body.description,
            currency=body.currency, valid_from=body.valid_from,
            valid_until=body.valid_until, max_redemptions=body.max_redemptions,
            max_per_user=body.max_per_user, first_time_only=body.first_time_only,
            min_amount_minor=body.min_amount_minor,
            applicable_plan_codes=body.applicable_plan_codes, actor_id=user.id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(status_code=409 if code == "coupon_exists" else 422, detail=code)
    return _coupon_admin_view(db, coupon)


@admin_router.patch("/coupons/{coupon_id}", response_model=schemas.CouponAdminOut)
def patch_coupon(
    coupon_id: int,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_MANAGE)),
):
    if set(body) != {"is_active"}:
        raise HTTPException(status_code=422, detail="only_is_active_supported")
    try:
        coupon = service.set_coupon_active(
            db, coupon_id=coupon_id, is_active=bool(body["is_active"]), actor_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _coupon_admin_view(db, coupon)


@admin_router.get("/report", response_model=list[schemas.CampaignReportOut])
def attribution_report(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    return service.campaign_report(db)


@admin_router.get("/plans", response_model=list[schemas.PlanOut])
def list_admin_plans(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    return service.list_public_plans(db)


@admin_router.get("/redemptions")
def list_redemptions(
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    page_size = min(max(page_size, 1), 200)
    query = db.query(service.BillingCouponRedemption).order_by(
        service.BillingCouponRedemption.id.desc()
    )
    if status:
        query = query.filter(service.BillingCouponRedemption.status == status)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    out = []
    for row in rows:
        coupon = db.get(service.BillingCoupon, row.coupon_id)
        out.append(
            {
                "id": row.id,
                "coupon_code": coupon.code if coupon else "",
                "user_id": row.user_id,
                "subscription_id": row.subscription_id,
                "status": row.status,
                "discount_granted_minor": row.discount_granted_minor,
                "trial_days_granted": row.trial_days_granted,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out


@admin_router.get("/subscriptions")
def list_subscriptions(
    user_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    page_size = min(max(page_size, 1), 200)
    query = db.query(service.BillingSubscription).order_by(service.BillingSubscription.id.desc())
    if user_id is not None:
        query = query.filter(service.BillingSubscription.user_id == user_id)
    if status:
        query = query.filter(service.BillingSubscription.status == status)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return [_sub_out(row).model_dump() for row in rows]


@admin_router.get("/payments")
def list_payments(
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_READ)),
):
    _ = user
    page_size = min(max(page_size, 1), 200)
    query = db.query(service.BillingPayment).order_by(service.BillingPayment.id.desc())
    if status:
        query = query.filter(service.BillingPayment.status == status)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "subscription_id": row.subscription_id,
            "plan_code": row.plan_code,
            "price_amount_minor": row.price_amount_minor,
            "discount_minor": row.discount_minor,
            "final_amount_minor": row.final_amount_minor,
            "currency": row.currency,
            "coupon_code": row.coupon_code,
            "provider": row.provider,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@admin_router.post("/plans", status_code=201)
def create_plan(
    body: schemas.PlanCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_MANAGE)),
):
    try:
        plan = service.create_plan(
            db, code=body.code, name_fa=body.name_fa,
            description_fa=body.description_fa,
            billing_interval=body.billing_interval,
            sort_order=body.sort_order, actor_id=user.id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(status_code=409 if code == "plan_exists" else 422, detail=code)
    return {"code": plan.code, "name_fa": plan.name_fa}


@admin_router.post("/plans/{plan_code}/prices", status_code=201)
def create_price(
    plan_code: str,
    body: schemas.PriceCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.BILLING_MANAGE)),
):
    try:
        price = service.create_price_version(
            db, plan_code=plan_code, amount_minor=body.amount_minor,
            currency=body.currency, billing_interval=body.billing_interval,
            actor_id=user.id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(status_code=404 if code == "plan_not_found" else 422, detail=code)
    return {"version": price.version, "amount_minor": price.amount_minor}
