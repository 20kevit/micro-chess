"""Admin operations: authz + real aggregations for new ops endpoints."""

from app.modules.users.models import User, UserRole


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _admin_token(client, db_session, username="ops_admin"):
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


def _player_token(client, username="ops_player"):
    _register(client, username=username)
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "secret123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


PATHS = [
    "/api/v1/admin/review-queue",
    "/api/v1/admin/dashboard-extended",
    "/api/v1/admin/analytics/retention",
    "/api/v1/admin/analytics/learning",
    "/api/v1/admin/analytics/recommendations",
    "/api/v1/admin/sales/overview",
    "/api/v1/admin/insights",
    "/api/v1/admin/system/health",
    "/api/v1/admin/support/stats",
]


def test_ops_anonymous_is_401(client):
    for path in PATHS:
        assert client.get(path).status_code == 401, path


def test_ops_player_is_403(client):
    token = _player_token(client)
    for path in PATHS:
        assert client.get(path, headers=_bearer(token)).status_code == 403, path


def test_ops_admin_ok_and_real_shapes(client, db_session):
    token = _admin_token(client, db_session)
    headers = _bearer(token)
    res = client.get("/api/v1/admin/review-queue", headers=headers)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
    res = client.get("/api/v1/admin/dashboard-extended", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["users_total"] >= 1
    assert "registrations" in body and "series" in body
    res = client.get("/api/v1/admin/analytics/retention", headers=headers)
    assert res.status_code == 200, res.text
    assert "cohorts" in res.json() and "offsets" in res.json()
    res = client.get("/api/v1/admin/analytics/learning", headers=headers)
    assert res.status_code == 200, res.text
    assert "exercise_usage" in res.json()
    res = client.get("/api/v1/admin/analytics/recommendations", headers=headers)
    assert res.status_code == 200, res.text
    assert "total" in res.json()
    res = client.get("/api/v1/admin/sales/overview", headers=headers)
    assert res.status_code == 200, res.text
    assert "revenue_minor" in res.json()
    res = client.get("/api/v1/admin/insights", headers=headers)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
    res = client.get("/api/v1/admin/system/health", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["database"]["reachable"] is True
    assert "schema_status" in res.json()
    res = client.get("/api/v1/admin/support/stats", headers=headers)
    assert res.status_code == 200, res.text
    assert "by_status" in res.json()


def test_audit_actor_filter(client, db_session):
    token = _admin_token(client, db_session, username="ops_admin_two")
    headers = _bearer(token)
    res = client.get("/api/v1/admin/audit?actor_id=999999", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_billing_admin_filters(client, db_session):
    token = _admin_token(client, db_session, username="ops_admin_three")
    headers = _bearer(token)
    assert client.get("/api/v1/admin/billing/plans", headers=headers).status_code == 200
    res = client.get("/api/v1/admin/billing/subscriptions?status=active", headers=headers)
    assert res.status_code == 200, res.text
    res = client.get("/api/v1/admin/billing/payments?status=verified", headers=headers)
    assert res.status_code == 200, res.text
    res = client.get("/api/v1/admin/billing/redemptions?status=applied", headers=headers)
    assert res.status_code == 200, res.text


def _admin_headers(client, db_session, username):
    return _bearer(_admin_token(client, db_session, username=username))


def test_commercial_toggles_require_admin(client, db_session):
    player = _bearer(_player_token(client, username="ops_shop_player"))
    for method, path in (
        ("patch", "/api/v1/admin/billing/campaigns/x"),
        ("patch", "/api/v1/admin/billing/plans/x"),
        ("patch", "/api/v1/admin/billing/prices/1"),
    ):
        assert client.request(method, path, json={"is_active": False}).status_code == 401
        assert client.request(method, path, json={"is_active": False}, headers=player).status_code == 403


def test_campaign_toggle_roundtrip(client, db_session):
    headers = _admin_headers(client, db_session, "ops_shop_admin")
    res = client.post(
        "/api/v1/admin/billing/campaigns",
        json={"slug": "ShopEvent", "name_fa": "رویداد", "source": "shop"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["slug"] == "shopevent"
    res = client.patch(
        "/api/v1/admin/billing/campaigns/shopevent", json={"is_active": False}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    res = client.patch(
        "/api/v1/admin/billing/campaigns/shopevent", json={"is_active": True}, headers=headers
    )
    assert res.json()["is_active"] is True
    assert client.patch(
        "/api/v1/admin/billing/campaigns/shopevent", json={"other": 1}, headers=headers
    ).status_code == 422
    assert client.patch(
        "/api/v1/admin/billing/campaigns/nope", json={"is_active": False}, headers=headers
    ).status_code == 404


def test_plan_and_price_toggle_preserve_history(client, db_session):
    headers = _admin_headers(client, db_session, "ops_plan_admin")
    assert client.post(
        "/api/v1/admin/billing/plans",
        json={"code": "Club", "name_fa": "باشگاهی"},
        headers=headers,
    ).status_code == 201
    res = client.post(
        "/api/v1/admin/billing/plans/club/prices",
        json={"amount_minor": 100000, "currency": "IRR", "billing_interval": "monthly"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    res = client.get("/api/v1/admin/billing/plans", headers=headers)
    assert res.status_code == 200, res.text
    club = next(row for row in res.json() if row["code"] == "club")
    assert len(club["prices"]) == 1
    price_id = club["prices"][0]["id"]
    assert club["prices"][0]["is_active"] is True
    res = client.patch(
        f"/api/v1/admin/billing/prices/{price_id}", json={"is_active": False}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    assert res.json()["amount_minor"] == 100000  # history untouched
    res = client.patch(
        "/api/v1/admin/billing/plans/club", json={"is_active": False}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    assert len(res.json()["prices"]) == 1  # versions preserved
    assert client.patch(
        "/api/v1/admin/billing/prices/999999", json={"is_active": False}, headers=headers
    ).status_code == 404


def test_coupon_admin_shows_plans_and_redemption_filter(client, db_session):
    headers = _admin_headers(client, db_session, "ops_coupon_admin")
    client.post(
        "/api/v1/admin/billing/campaigns",
        json={"slug": "coupon-camp", "name_fa": "کمپین", "source": "x"},
        headers=headers,
    )
    res = client.post(
        "/api/v1/admin/billing/coupons",
        json={"code": "shop10", "discount_type": "percent", "discount_value": 10,
              "campaign_slug": "coupon-camp", "applicable_plan_codes": ["free"]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["code"] == "SHOP10"
    assert body["applicable_plan_codes"] == ["free"]
    assert body["total_redemptions"] == 0
    res = client.get("/api/v1/admin/billing/redemptions?coupon_code=SHOP10", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == []
    res = client.get("/api/v1/admin/billing/redemptions?coupon_code=NOPE", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_subscription_and_payment_admin_visibility(client, db_session):
    headers = _admin_headers(client, db_session, "ops_vis_admin")
    res = client.get("/api/v1/admin/billing/subscriptions", headers=headers)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
    if res.json():
        assert "user_id" in res.json()[0]
    res = client.get("/api/v1/admin/billing/payments", headers=headers)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
    if res.json():
        assert "failure_reason" in res.json()[0]
        assert "provider_ref" in res.json()[0]
