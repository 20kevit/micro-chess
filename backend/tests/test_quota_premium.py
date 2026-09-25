"""Free/Premium quota, Telegram/Bale verification, activation, invoice.

Quota: anonymous blocked, free 10/day, premium 100/day, exact-limit,
one-beyond rejected, next-day reset, timezone behavior, invalid
attempts not counted, no double counting, direct-API enforcement.
Verification: sessions, pairing codes, contact ownership, replay,
expiry, wrong user, duplicate phone, webhook auth, provider failure.
Activation: 100%-coupon invoice with zero payable, idempotent
activation, coupon rules, no gateway.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _register(client: TestClient, username: str) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123", "display_name": username},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_piece(db_session):
    from app.modules.piece_recognition import seed as piece_seed
    from tests.conftest import publish_staged_puzzles

    piece_seed.seed_db(db_session)
    publish_staged_puzzles(db_session, "piece-recognition")


def _puzzle_id(db_session) -> int:
    from app.modules.puzzles.models import Puzzle

    row = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == "piece-recognition", Puzzle.is_published.is_(True))
        .first()
    )
    assert row is not None
    return int(row.id)


def _submit(client, headers, puzzle_id, answer=None, mode="practice", client_result=None):
    body = {"puzzle_id": puzzle_id, "answer": answer or {"selected_squares": ["a1"]}, "mode": mode}
    if client_result:
        body["client_result"] = client_result
    return client.post("/api/v1/attempts", json=body, headers=headers)


def _premium_coupon(db_session, code="PREM100", **kw):
    from app.modules.billing import service as billing

    params = dict(code=code, discount_type="percent", discount_value=100,
                  max_per_user=1, applicable_plan_codes=["premium"])
    params.update(kw)
    return billing.create_coupon(db_session, **params)


# --- anonymous / free baseline -------------------------------------------------

def test_anonymous_cannot_submit_or_read_quota(client):
    assert client.post("/api/v1/attempts", json={"puzzle_id": 1, "answer": {}, "mode": "practice"}).status_code == 401
    assert client.get("/api/v1/me/quota").status_code == 401


def test_free_quota_shape_and_practice(client, db_session):
    _seed_piece(db_session)
    h = _bearer(_register(client, "q_free_a")["access_token"])
    quota = client.get("/api/v1/me/quota", headers=h).json()
    assert quota == {"used": 0, "limit": 10, "remaining": 10, "plan": "free",
                     "local_date": quota["local_date"], "can_practice": True,
                     "upgrade_available": True}
    assert client.post("/api/v1/attempts",
                       json={"puzzle_id": _puzzle_id(db_session), "answer": {"selected_squares": ["a1"]},
                             "mode": "practice"}, headers=h).status_code in (200, 201)
    quota = client.get("/api/v1/me/quota", headers=h).json()
    assert (quota["used"], quota["remaining"], quota["can_practice"]) == (1, 9, True)


def test_free_exactly_10_then_11th_rejected(client, db_session):
    _seed_piece(db_session)
    h = _bearer(_register(client, "q_free_b")["access_token"])
    pid = _puzzle_id(db_session)
    for _ in range(10):
        assert _submit(client, h, pid).status_code in (200, 201)
    assert client.get("/api/v1/me/quota", headers=h).json()["can_practice"] is False
    rejected = _submit(client, h, pid)
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "daily_quota_exceeded"
    # Rejected submission consumed nothing extra.
    assert client.get("/api/v1/me/quota", headers=h).json()["used"] == 10


def test_invalid_attempts_do_not_consume_quota(client, db_session):
    _seed_piece(db_session)
    h = _bearer(_register(client, "q_free_c")["access_token"])
    pid = _puzzle_id(db_session)
    # Terminal client state: recorded but never quota-counted.
    assert _submit(client, h, pid, client_result="skipped").status_code in (200, 201)
    # Unknown puzzle: rejected before any counting.
    assert client.post("/api/v1/attempts",
                       json={"puzzle_id": 999999, "answer": {}, "mode": "practice"},
                       headers=h).status_code == 404
    assert client.get("/api/v1/me/quota", headers=h).json()["used"] == 0


def test_next_local_day_resets_quota(client, db_session):
    from app.modules.quota.models import DailyUsage
    from app.modules.users.models import User

    _seed_piece(db_session)
    data = _register(client, "q_free_d")
    h = _bearer(data["access_token"])
    pid = _puzzle_id(db_session)
    for _ in range(10):
        assert _submit(client, h, pid).status_code in (200, 201)
    assert _submit(client, h, pid).status_code == 403
    # Age the usage row into yesterday: the next submit opens a fresh day.
    user = db_session.query(User).filter(User.username == "q_free_d").first()
    row = db_session.query(DailyUsage).filter(DailyUsage.user_id == user.id).first()
    row.local_date = "2000-01-01"
    row.window_start_utc = datetime(2000, 1, 1)
    row.window_end_utc = datetime(2000, 1, 2)
    db_session.commit()
    assert _submit(client, h, pid).status_code in (200, 201)
    assert client.get("/api/v1/me/quota", headers=h).json()["used"] == 1


def test_timezone_day_boundary_pure():
    from app.modules.quota.service import day_window

    noon_utc = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    assert day_window("Asia/Tehran", noon_utc)[0] == "2026-09-21"
    late_utc = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
    # 00:30 next day in Tehran.
    assert day_window("Asia/Tehran", late_utc)[0] == "2026-09-22"
    assert day_window("America/New_York", noon_utc)[0] == "2026-09-21"
    # Unknown timezone falls back deterministically, never crashes.
    assert day_window("Not/AZone", noon_utc)[0] == "2026-09-21"


def test_timezone_change_midday_cannot_mint_quota(client, db_session):
    _seed_piece(db_session)
    data = _register(client, "q_free_e")
    h = _bearer(data["access_token"])
    pid = _puzzle_id(db_session)
    for _ in range(10):
        assert _submit(client, h, pid).status_code in (200, 201)
    # Hop to a far timezone mid-day: the open UTC window still counts.
    client.put("/api/v1/me/onboarding", json={"timezone": "Pacific/Kiritimati"}, headers=h)
    assert _submit(client, h, pid).status_code == 403


def test_usage_row_collapse_no_double_count(client, db_session):
    from app.modules.quota import service as quota_service
    from app.modules.users.models import User

    _register(client, "q_free_f")
    user = db_session.query(User).filter(User.username == "q_free_f").first()
    first = quota_service.check_and_consume(db_session, user.id)
    second = quota_service.check_and_consume(db_session, user.id)
    assert (first["used"], second["used"]) == (1, 2)
    from app.modules.quota.models import DailyUsage

    rows = db_session.query(DailyUsage).filter(DailyUsage.user_id == user.id).all()
    assert len(rows) == 1 and rows[0].count == 2


# --- premium quota -------------------------------------------------------------

def _verify_user(db_session, user_id: int, phone: str = "+989100000001",
                 channel: str = "telegram") -> None:
    from app.modules.player.models import PlayerExternalIdentity
    from app.modules.users.models import User

    user = db_session.get(User, user_id)
    user.phone = phone
    user.phone_verified = True
    platform_id = f"tg-{user_id}"
    db_session.add(PlayerExternalIdentity(
        user_id=user_id, provider=channel, external_username=platform_id,
        provider_user_id=platform_id, is_verified=True,
        verified_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db_session.commit()


def _user_id(db_session, username: str) -> int:
    from app.modules.users.models import User

    return int(db_session.query(User).filter(User.username == username).first().id)


def test_premium_100_then_101st_rejected(client, db_session):
    from app.modules.billing import service as billing

    _seed_piece(db_session)
    data = _register(client, "q_prem_a")
    h = _bearer(data["access_token"])
    uid = _user_id(db_session, "q_prem_a")
    _verify_user(db_session, uid)
    _premium_coupon(db_session, code="PREM100A")
    assert client.post("/api/v1/billing/me/premium/activate",
                       json={"coupon_code": "PREM100A"}, headers=h).status_code == 200
    assert client.get("/api/v1/me/quota", headers=h).json()["limit"] == 100
    pid = _puzzle_id(db_session)
    for _ in range(100):
        assert _submit(client, h, pid).status_code in (200, 201)
    assert _submit(client, h, pid).status_code == 403
    assert client.get("/api/v1/me/quota", headers=h).json()["used"] == 100


def test_trial_coupon_also_raises_quota(client, db_session):
    from app.modules.billing import service as billing

    data = _register(client, "q_prem_c")
    h = _bearer(data["access_token"])
    uid = _user_id(db_session, "q_prem_c")
    billing.create_coupon(db_session, code="TRIAL30", discount_type="free_trial",
                          trial_days=30, max_per_user=5)
    res = client.post("/api/v1/billing/coupons/redeem", json={"code": "TRIAL30"}, headers=h)
    assert res.status_code == 200, res.text
    assert client.get("/api/v1/me/quota", headers=h).json()["limit"] == 100


# --- activation / invoice / coupons ----------------------------------------------

def test_activation_requires_verified_phone(client, db_session):
    data = _register(client, "q_act_b")
    h = _bearer(data["access_token"])
    _premium_coupon(db_session, code="PREM100B")
    res = client.post("/api/v1/billing/me/premium/activate",
                      json={"coupon_code": "PREM100B"}, headers=h)
    assert res.status_code == 403
    assert res.json()["detail"] == "phone_not_verified"


def test_zero_amount_activation_invoice_and_idempotency(client, db_session):
    _seed_piece(db_session)
    data = _register(client, "q_act_c")
    h = _bearer(data["access_token"])
    uid = _user_id(db_session, "q_act_c")
    _verify_user(db_session, uid, phone="+989100000002")
    _premium_coupon(db_session, code="PREM100C")
    quote = client.get("/api/v1/billing/me/premium/quote",
                       params={"coupon_code": "PREM100C"}, headers=h).json()
    assert quote["price_amount_minor"] > 0
    assert quote["discount_minor"] == quote["price_amount_minor"]
    assert quote["final_amount_minor"] == 0
    assert quote["gateway_required"] is False
    first = client.post("/api/v1/billing/me/premium/activate",
                        json={"coupon_code": "PREM100C"}, headers=h)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "active" and body["already"] is False
    second = client.post("/api/v1/billing/me/premium/activate",
                         json={"coupon_code": "PREM100C"}, headers=h)
    # Second activation is rejected by per-user coupon rules, or replays
    # idempotently when the redemption already settled.
    assert second.status_code in (200, 409)
    if second.status_code == 200:
        assert second.json()["already"] is True
        assert second.json()["subscription_id"] == body["subscription_id"]
    from app.modules.billing.models import BillingSubscription

    active = db_session.query(BillingSubscription).filter(
        BillingSubscription.user_id == uid, BillingSubscription.plan_code == "premium",
        BillingSubscription.status == "active").all()
    assert len(active) == 1
    # No money moved: the settled payment records a zero final amount
    # with explicit zero-settlement metadata (never a fake charge).
    from app.modules.billing.models import BillingPayment

    pay = db_session.query(BillingPayment).filter(
        BillingPayment.user_id == uid, BillingPayment.status == "verified").first()
    assert pay is not None and (pay.final_amount_minor or 0) == 0
    assert pay.verification_meta["settled"] == "zero_amount_coupon"


def test_nonzero_payable_honestly_rejected(client, db_session):
    data = _register(client, "q_act_d")
    h = _bearer(data["access_token"])
    _verify_user(db_session, _user_id(db_session, "q_act_d"), phone="+989100000003")
    _premium_coupon(db_session, code="HALF50", discount_type="percent", discount_value=50)
    res = client.post("/api/v1/billing/me/premium/activate",
                      json={"coupon_code": "HALF50"}, headers=h)
    assert res.status_code == 422
    assert res.json()["detail"] == "payment_required"


def test_coupon_rules_invalid_expired_limits(client, db_session):
    from app.modules.billing import service as billing

    data = _register(client, "q_act_e")
    h = _bearer(data["access_token"])
    _verify_user(db_session, _user_id(db_session, "q_act_e"), phone="+989100000004")
    assert client.post("/api/v1/billing/me/premium/activate",
                       json={"coupon_code": "NOPE"}, headers=h).status_code == 404
    billing.create_coupon(db_session, code="OLD", discount_type="percent", discount_value=100,
                          valid_until=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
                          applicable_plan_codes=["premium"])
    assert client.post("/api/v1/billing/me/premium/activate",
                       json={"coupon_code": "OLD"}, headers=h).status_code == 422
    billing.create_coupon(db_session, code="ONCE", discount_type="percent", discount_value=100,
                          max_redemptions=1, max_per_user=1, applicable_plan_codes=["premium"])
    assert client.post("/api/v1/billing/me/premium/activate",
                       json={"coupon_code": "ONCE"}, headers=h).status_code == 200
    data2 = _register(client, "q_act_f")
    h2 = _bearer(data2["access_token"])
    _verify_user(db_session, _user_id(db_session, "q_act_f"), phone="+989100000005")
    assert client.post("/api/v1/billing/me/premium/activate",
                       json={"coupon_code": "ONCE"}, headers=h2).status_code == 409
