"""Billing domain: plans, subscriptions, entitlements, coupons, attribution, payments.

Backend is authoritative: every commercial value is computed server-side.
These tests also attempt common bypasses (client price math, replays,
direct premium calls) and assert the server rejects them.
"""

from datetime import datetime, timedelta, timezone

from app.modules.billing import service as billing
from app.modules.users.models import User, UserRole


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _user_id(db_session, username):
    return db_session.query(User).filter(User.username == username).one().id


def _admin_token(client, db_session, username="the_admin"):
    _register(client, username=username)
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, "ADMIN")) is None:
        db_session.add(UserRole(user_id=user.id, role="ADMIN"))
        db_session.commit()
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123", "role": "ADMIN"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _trial_coupon(db_session, code="ABADEH1405", campaign="abadeh-chess-group", days=30):
    billing.create_campaign(
        db_session, slug=campaign, name_fa="گروه آباده",
        source="chess_group", medium="telegram", content="september-2026",
    )
    return billing.create_coupon(
        db_session, code=code, discount_type="free_trial", trial_days=days,
        campaign_slug=campaign, description="group promo",
    )


# --- plans & prices -----------------------------------------------------------


def test_default_plans_seed_free_and_premium_without_price(client, db_session):
    res = client.get("/api/v1/billing/plans")
    assert res.status_code == 200, res.text
    plans = {p["code"]: p for p in res.json()}
    assert set(plans) == {"free", "premium"}
    assert plans["free"]["prices"] and plans["free"]["prices"][0]["amount_minor"] == 0
    # No commercial price invented: premium ships with no price row.
    assert plans["premium"]["prices"] == []
    assert billing.paid_checkout_enabled(db_session) is False


def test_price_versions_are_immutable_and_snapshot_history(db_session):
    billing.ensure_default_plans(db_session)
    v1 = billing.create_price_version(
        db_session, plan_code="premium", amount_minor=1_000_000, currency="IRR"
    )
    assert v1.version == 1
    from app.modules.users.models import User as _User

    user = _User(username="hist_user", password_hash="x", display_name="h")
    db_session.add(user)
    db_session.commit()
    sub = billing.BillingSubscription(
        user_id=user.id, plan_id=v1.plan_id, price_id=v1.id, status="active",
        source="paid", plan_code="premium", price_amount_minor=v1.amount_minor,
        price_currency="IRR", price_interval="monthly",
    )
    db_session.add(sub)
    db_session.commit()
    v2 = billing.create_price_version(
        db_session, plan_code="premium", amount_minor=2_000_000, currency="IRR"
    )
    assert v2.version == 2
    db_session.refresh(sub)
    # Historical row keeps the price it was created under.
    assert sub.price_amount_minor == 1_000_000
    active = billing.get_active_price(db_session, v1.plan_id)
    assert active.version == 2 and active.amount_minor == 2_000_000


def test_create_plan_rejects_duplicates_and_bad_intervals(db_session):
    billing.ensure_default_plans(db_session)
    try:
        billing.create_plan(db_session, code="free", name_fa="x")
    except ValueError as exc:
        assert str(exc) == "plan_exists"
    else:
        raise AssertionError("expected plan_exists")
    try:
        billing.create_plan(db_session, code="gold", name_fa="x", billing_interval="weekly")
    except ValueError as exc:
        assert str(exc) == "invalid_interval"
    else:
        raise AssertionError("expected invalid_interval")


# --- free beta -----------------------------------------------------------------


def test_registration_still_works_without_payment(client, db_session):
    res = _register(client, username="beta_user")
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "beta_user")
    sub = billing.ensure_free_subscription(db_session, uid)
    assert sub.status == "active" and sub.plan_code == "free"
    access = billing.subscription_access(db_session, uid)
    assert access["has_paid_access"] is False
    assert "basic_training" in access["features"]
    assert "advanced_analytics" not in access["features"]


def test_registration_with_invalid_coupon_still_succeeds(client, db_session):
    res = _register(client, username="badcoupon", coupon_code="NOPE404")
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "badcoupon")
    access = billing.subscription_access(db_session, uid)
    assert access["plan_code"] == "free" and access["has_paid_access"] is False


def test_ensure_free_subscription_is_idempotent(db_session):
    from app.modules.users.models import User as _User

    user = _User(username="idem_free", password_hash="x", display_name="i")
    db_session.add(user)
    db_session.commit()
    first = billing.ensure_free_subscription(db_session, user.id)
    second = billing.ensure_free_subscription(db_session, user.id)
    assert first.id == second.id


# --- coupons -------------------------------------------------------------------


def test_free_trial_coupon_grants_trial_and_redemption(client, db_session):
    _trial_coupon(db_session)
    res = _register(client, username="abadeh_user", coupon_code="abadeh1405")
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "abadeh_user")
    access = billing.subscription_access(db_session, uid)
    assert access["has_paid_access"] is True
    assert access["plan_code"] == "premium" and access["status"] == "trialing"
    assert "advanced_analytics" in access["features"]
    redemptions = (
        db_session.query(billing.BillingCouponRedemption)
        .filter(billing.BillingCouponRedemption.user_id == uid)
        .all()
    )
    assert len(redemptions) == 1
    assert redemptions[0].trial_days_granted == 30
    assert redemptions[0].status == "applied"


def test_coupon_codes_are_case_insensitive(db_session):
    billing.ensure_default_plans(db_session)
    _trial_coupon(db_session, code="Shiraz1405")
    quote = billing.validate_coupon(db_session, code="  shiraz1405 ", user_id=9999)
    assert quote["coupon"].code == "SHIRAZ1405"


def test_expired_inactive_and_future_coupons_rejected(db_session):
    billing.ensure_default_plans(db_session)
    now = _utcnow()
    billing.create_coupon(
        db_session, code="OLDCODE", discount_type="free_trial", trial_days=7,
        valid_until=now - timedelta(days=1),
    )
    billing.create_coupon(
        db_session, code="FUTURE", discount_type="free_trial", trial_days=7,
        valid_from=now + timedelta(days=1),
    )
    inactive = billing.create_coupon(
        db_session, code="OFFCODE", discount_type="free_trial", trial_days=7,
    )
    billing.set_coupon_active(db_session, coupon_id=inactive.id, is_active=False)
    for code, expected in [
        ("OLDCODE", "coupon_expired"),
        ("FUTURE", "coupon_not_yet_valid"),
        ("OFFCODE", "coupon_inactive"),
        ("MISSING", "coupon_not_found"),
    ]:
        try:
            billing.validate_coupon(db_session, code=code, user_id=1)
        except ValueError as exc:
            assert str(exc) == expected, (code, str(exc))
        else:
            raise AssertionError(f"expected {expected} for {code}")


def test_max_redemptions_and_per_user_limit(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="ONCE", discount_type="free_trial", trial_days=7,
        max_redemptions=1, max_per_user=1,
    )
    users = []
    for name in ("u_one", "u_two"):
        user = _User(username=name, password_hash="x", display_name=name)
        db_session.add(user)
        db_session.commit()
        users.append(user)
    billing.redeem_coupon(db_session, user_id=users[0].id, code="ONCE")
    # Same user again -> per-user limit (validated before global cap).
    try:
        billing.redeem_coupon(
            db_session, user_id=users[0].id, code="ONCE",
            idempotency_key="replay-check-1",
        )
    except ValueError as exc:
        assert str(exc) in ("per_user_limit", "trial_already_used"), str(exc)
    else:
        raise AssertionError("expected per-user rejection")
    # Second user -> global cap exhausted.
    try:
        billing.redeem_coupon(db_session, user_id=users[1].id, code="ONCE")
    except ValueError as exc:
        assert str(exc) == "max_redemptions_exhausted", str(exc)
    else:
        raise AssertionError("expected max_redemptions_exhausted")


def test_second_trial_coupon_rejected_one_trial_per_user(client, db_session):
    _trial_coupon(db_session, code="FIRST30", campaign="camp-one", days=30)
    _trial_coupon(db_session, code="SECOND30", campaign="camp-two", days=30)
    res = _register(client, username="trial_once", coupon_code="FIRST30")
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "trial_once")
    token = res.json()["access_token"]
    res2 = client.post(
        "/api/v1/billing/coupons/redeem", json={"code": "SECOND30"},
        headers=_bearer(token),
    )
    assert res2.status_code == 409, res2.text
    assert res2.json()["detail"] == "trial_already_used"
    redemptions = (
        db_session.query(billing.BillingCouponRedemption)
        .filter(billing.BillingCouponRedemption.user_id == uid)
        .all()
    )
    assert len(redemptions) == 1


def test_wrong_plan_coupon_rejected(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="FREEBIE", discount_type="free_trial", trial_days=7,
        applicable_plan_codes=["free"],
    )
    user = _User(username="plan_user", password_hash="x", display_name="p")
    db_session.add(user)
    db_session.commit()
    try:
        billing.validate_coupon(db_session, code="FREEBIE", user_id=user.id, plan_code="premium")
    except ValueError as exc:
        assert str(exc) == "wrong_plan", str(exc)
    else:
        raise AssertionError("expected wrong_plan")
    try:
        billing.validate_coupon(db_session, code="FREEBIE", user_id=user.id, plan_code="nope")
    except ValueError as exc:
        assert str(exc) == "wrong_plan", str(exc)
    else:
        raise AssertionError("expected wrong_plan for unknown plan")


def test_invalid_discount_values_rejected(db_session):
    billing.ensure_default_plans(db_session)
    for kwargs, expected in [
        ({"discount_type": "percent", "discount_value": 0}, "invalid_discount"),
        ({"discount_type": "percent", "discount_value": 101}, "invalid_discount"),
        ({"discount_type": "fixed", "discount_value": 0}, "invalid_discount"),
        ({"discount_type": "free_trial", "trial_days": 0}, "invalid_discount"),
        ({"discount_type": "mystery"}, "invalid_discount"),
    ]:
        try:
            billing.create_coupon(db_session, code=f"BAD{expected}{id(kwargs)}"[:60], **kwargs)
        except ValueError as exc:
            assert str(exc) == expected, str(exc)
        else:
            raise AssertionError(f"expected {expected}")


def test_percent_coupon_without_price_is_unavailable(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="PCT20", discount_type="percent", discount_value=20,
    )
    user = _User(username="pct_user", password_hash="x", display_name="p")
    db_session.add(user)
    db_session.commit()
    try:
        billing.validate_coupon(db_session, code="PCT20", user_id=user.id)
    except ValueError as exc:
        assert str(exc) == "plan_price_unavailable", str(exc)
    else:
        raise AssertionError("expected plan_price_unavailable")


def test_percent_coupon_with_price_creates_pending_not_active(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_price_version(
        db_session, plan_code="premium", amount_minor=1_000_000
    )
    billing.create_coupon(
        db_session, code="PCT20", discount_type="percent", discount_value=20,
    )
    user = _User(username="pend_user", password_hash="x", display_name="p")
    db_session.add(user)
    db_session.commit()
    quote = billing.validate_coupon(db_session, code="PCT20", user_id=user.id)
    assert quote["discount_minor"] == 200_000
    assert quote["final_amount_minor"] == 800_000
    outcome = billing.redeem_coupon(db_session, user_id=user.id, code="PCT20")
    sub = db_session.get(billing.BillingSubscription, outcome["subscription_id"])
    assert sub.status == "pending"
    # Pending payment intent grants nothing until provider verification.
    access = billing.subscription_access(db_session, user.id)
    assert access["has_paid_access"] is False
    payment = (
        db_session.query(billing.BillingPayment)
        .filter(billing.BillingPayment.subscription_id == sub.id)
        .one()
    )
    assert payment.status == "pending" and payment.provider == "none"
    assert payment.final_amount_minor == 800_000
    assert payment.price_amount_minor == 1_000_000  # snapshot


def test_redeem_idempotency_key_replays_without_duplicates(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="IDEM30", discount_type="free_trial", trial_days=30,
    )
    user = _User(username="idem_user", password_hash="x", display_name="i")
    db_session.add(user)
    db_session.commit()
    first = billing.redeem_coupon(
        db_session, user_id=user.id, code="IDEM30", idempotency_key="key-123"
    )
    second = billing.redeem_coupon(
        db_session, user_id=user.id, code="IDEM30", idempotency_key="key-123"
    )
    assert first["already"] is False and second["already"] is True
    assert first["redemption"].id == second["redemption"].id
    count = (
        db_session.query(billing.BillingCouponRedemption)
        .filter(billing.BillingCouponRedemption.user_id == user.id)
        .count()
    )
    assert count == 1


# --- attribution ---------------------------------------------------------------


def test_registration_attribution_links_campaign_coupon_trial(client, db_session):
    _trial_coupon(db_session)
    res = _register(
        client, username="attrib_user", coupon_code="ABADEH1405",
        landing_path="/?coupon=ABADEH1405",
    )
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "attrib_user")
    row = (
        db_session.query(billing.BillingAttribution)
        .filter(billing.BillingAttribution.user_id == uid)
        .one()
    )
    # Coupon implies its campaign even though the URL carried only a code.
    assert row.first_coupon_code == "ABADEH1405"
    assert row.first_source == "chess_group"
    assert row.first_medium == "telegram"
    assert row.first_landing_path == "/?coupon=ABADEH1405"
    campaign = db_session.query(billing.BillingCampaign).filter(
        billing.BillingCampaign.slug == "abadeh-chess-group"
    ).one()
    assert row.first_campaign_id == campaign.id


def test_first_touch_preserved_last_touch_updates(client, db_session):
    billing.create_campaign(db_session, slug="instagram", name_fa="اینستا", source="social")
    billing.create_campaign(db_session, slug="telegram", name_fa="تلگرام", source="social")
    res = _register(client, username="touch_user", campaign_slug="instagram")
    assert res.status_code == 201, res.text
    uid = _user_id(db_session, "touch_user")
    token = res.json()["access_token"]
    res2 = client.post(
        "/api/v1/billing/me/attribution",
        json={"campaign_slug": "telegram"},
        headers=_bearer(token),
    )
    assert res2.status_code == 204, res2.text
    row = (
        db_session.query(billing.BillingAttribution)
        .filter(billing.BillingAttribution.user_id == uid)
        .one()
    )
    insta = billing.get_campaign_by_slug(db_session, "instagram")
    tele = billing.get_campaign_by_slug(db_session, "telegram")
    assert row.first_campaign_id == insta.id  # permanent
    assert row.last_campaign_id == tele.id  # informational


def test_campaign_report_answers_marketing_questions(client, db_session):
    _trial_coupon(db_session)
    _register(client, username="rep_a", coupon_code="ABADEH1405")
    _register(client, username="rep_b", coupon_code="ABADEH1405")
    report = billing.campaign_report(db_session)
    abadeh = next(r for r in report if r["slug"] == "abadeh-chess-group")
    assert abadeh["registrations"] == 2
    assert abadeh["redemptions"] == 2
    assert abadeh["trials"] == 2
    assert abadeh["paid"] == 0


# --- entitlements & lifecycle ----------------------------------------------------


def test_expired_trial_loses_paid_access(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="SHORT7", discount_type="free_trial", trial_days=7,
    )
    user = _User(username="expire_user", password_hash="x", display_name="e")
    db_session.add(user)
    db_session.commit()
    billing.redeem_coupon(db_session, user_id=user.id, code="SHORT7")
    sub = billing.active_subscription_for(db_session, user.id)
    assert sub is not None and sub.status == "trialing"
    # Simulate time passing: trial end in the past, then resolve.
    sub.trial_ends_at = _utcnow() - timedelta(seconds=1)
    sub.current_period_end = sub.trial_ends_at
    db_session.commit()
    access = billing.subscription_access(db_session, user.id)
    assert access["has_paid_access"] is False
    assert access["plan_code"] == "free"
    events = (
        db_session.query(billing.BillingSubscriptionEvent)
        .filter(billing.BillingSubscriptionEvent.subscription_id == sub.id)
        .all()
    )
    assert {e.to_status for e in events} >= {"trialing", "expired"}


def test_cancel_keeps_access_until_period_end(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_coupon(
        db_session, code="CANCEL30", discount_type="free_trial", trial_days=30,
    )
    user = _User(username="cancel_user", password_hash="x", display_name="c")
    db_session.add(user)
    db_session.commit()
    billing.redeem_coupon(db_session, user_id=user.id, code="CANCEL30")
    sub = billing.active_subscription_for(db_session, user.id)
    cancelled = billing.cancel_subscription(
        db_session, user_id=user.id, subscription_id=sub.id
    )
    assert cancelled.status == "cancelled"
    # Still inside the paid period: access retained.
    still = billing.active_subscription_for(db_session, user.id)
    assert still is not None and still.id == sub.id
    # After the period: expired, free fallback.
    cancelled.current_period_end = _utcnow() - timedelta(seconds=1)
    db_session.commit()
    access = billing.subscription_access(db_session, user.id)
    assert access["plan_code"] == "free"


def test_premium_endpoint_forbidden_for_free_allowed_for_trial(client, db_session):
    _trial_coupon(db_session, code="GATE30", campaign="gate-camp", days=30)
    free_token = _register(client, username="gate_free").json()["access_token"]
    res = client.get("/api/v1/billing/me/advanced-overview", headers=_bearer(free_token))
    assert res.status_code == 403, res.text
    assert res.json()["detail"] == "premium_required"
    trial_token = _register(client, username="gate_trial", coupon_code="GATE30").json()["access_token"]
    res2 = client.get("/api/v1/billing/me/advanced-overview", headers=_bearer(trial_token))
    assert res2.status_code == 200, res2.text


def test_billing_self_endpoints_require_auth(client):
    assert client.get("/api/v1/billing/me/subscription").status_code == 401
    assert client.get("/api/v1/billing/me/entitlements").status_code == 401
    assert client.post("/api/v1/billing/coupons/redeem", json={"code": "X"}).status_code == 401


def test_client_cannot_set_price_or_discount(client, db_session):
    """No price/discount/trial field is accepted from the client: quotes
    come from the server price table, and unknown body keys are ignored."""
    _trial_coupon(db_session, code="HONEST30", campaign="honest-camp", days=30)
    token = _register(client, username="honest_user").json()["access_token"]
    res = client.post(
        "/api/v1/billing/coupons/validate",
        json={"code": "HONEST30", "plan_code": "premium",
              "price": 1, "discount": 999999, "trial_days": 3650},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    quote = res.json()
    assert quote["trial_days"] == 30  # server value, not 3650
    assert quote["discount_minor"] == 0


# --- payments --------------------------------------------------------------------


def test_paid_activation_requires_verified_payment(db_session):
    from app.modules.users.models import User as _User

    billing.ensure_default_plans(db_session)
    billing.create_price_version(db_session, plan_code="premium", amount_minor=500_000)
    user = _User(username="pay_user", password_hash="x", display_name="p")
    db_session.add(user)
    db_session.commit()
    payment = billing.BillingPayment(
        user_id=user.id, plan_code="premium", price_amount_minor=500_000,
        discount_minor=0, final_amount_minor=500_000, currency="IRR",
        provider="none", status="pending", idempotency_key="pay-test-1",
    )
    db_session.add(payment)
    db_session.commit()
    try:
        billing.activate_paid_subscription(db_session, payment_id=payment.id)
    except ValueError as exc:
        assert str(exc) == "payment_not_verified", str(exc)
    else:
        raise AssertionError("browser-claim activation must fail")
    # Simulate a provider-verified webhook (server-to-server).
    payment.status = "verified"
    payment.provider_ref = "proof-123"
    db_session.commit()
    sub = billing.activate_paid_subscription(db_session, payment_id=payment.id)
    assert sub.status == "active" and sub.source == "paid"
    assert sub.price_amount_minor == 500_000  # snapshot, not live lookup
    access = billing.subscription_access(db_session, user.id)
    assert access["has_paid_access"] is True


def test_null_provider_never_verifies():
    provider = billing.get_provider()
    assert provider.code == "none"
    try:
        provider.create_intent(
            amount_minor=100, currency="IRR",
            idempotency_key="k", metadata={},
        )
    except Exception as exc:
        assert "not_configured" in str(exc)
    else:
        raise AssertionError("NullProvider must fail closed")


# --- admin -------------------------------------------------------------------------


def test_admin_manages_campaigns_and_coupons_player_denied(client, db_session):
    admin = _bearer(_admin_token(client, db_session))
    player = _bearer(_register(client, username="regular").json()["access_token"])
    # Player is denied.
    assert client.post(
        "/api/v1/admin/billing/campaigns", json={"slug": "x"}, headers=player
    ).status_code == 403
    assert client.post(
        "/api/v1/admin/billing/coupons",
        json={"code": "X", "discount_type": "free_trial", "trial_days": 7},
        headers=player,
    ).status_code == 403
    # Admin creates campaign + coupon, then deactivates the coupon.
    res = client.post(
        "/api/v1/admin/billing/campaigns",
        json={"slug": "coach-ali", "name_fa": "مربی علی", "source": "coach"},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    res = client.post(
        "/api/v1/admin/billing/coupons",
        json={"code": "COACHALI", "discount_type": "free_trial",
              "trial_days": 30, "campaign_slug": "coach-ali",
              "max_redemptions": 100},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    coupon_id = res.json()["id"]
    res = client.get("/api/v1/admin/billing/coupons", headers=admin)
    assert res.status_code == 200 and any(c["code"] == "COACHALI" for c in res.json())
    res = client.patch(
        f"/api/v1/admin/billing/coupons/{coupon_id}",
        json={"is_active": False}, headers=admin,
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    res = client.get("/api/v1/admin/billing/report", headers=admin)
    assert res.status_code == 200, res.text
    assert any(r["slug"] == "coach-ali" for r in res.json())
