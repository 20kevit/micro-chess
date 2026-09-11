"""Foundation: capability registry, auth primitives, rate-limit hooks."""

import pytest

from app.core.capabilities import (
    Capability,
    Role,
    has_capability,
    require_capability,
    role_for_user,
)
from app.core.rate_limit import RateLimiter
from app.core.security import hash_password, validate_password, verify_password


def _register(client, email="kid@example.com", password="secret123"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Kid"},
    )


def test_player_capabilities_granted_and_admin_denied():
    assert has_capability(Role.PLAYER, Capability.EXERCISES_READ)
    assert has_capability(Role.PLAYER, Capability.PUZZLES_READ)
    assert has_capability(Role.PLAYER, Capability.ATTEMPTS_SUBMIT)
    assert has_capability(Role.PLAYER, Capability.USERS_READ)
    assert not has_capability(Role.PLAYER, Capability.USERS_MANAGE)
    assert not has_capability(Role.PLAYER, Capability.PUZZLES_PUBLISH)
    # Future roles grant nothing until Phase 2 persists them (fail closed).
    assert not has_capability(Role.ADMIN, Capability.USERS_MANAGE)


def test_phase1_users_act_as_player():
    assert role_for_user(object()) is Role.PLAYER


def test_require_capability_anonymous_and_forbidden():
    from fastapi import HTTPException

    check = require_capability(Capability.USERS_MANAGE)
    with pytest.raises(HTTPException) as exc:
        check(None)
    assert exc.value.status_code == 401

    check_open = require_capability(Capability.ATTEMPTS_SUBMIT, allow_anonymous=True)
    assert check_open(None) is None

    with pytest.raises(HTTPException) as exc2:
        check(object())
    assert exc2.value.status_code == 403


def test_password_policy_boundaries():
    with pytest.raises(ValueError, match="password_too_short"):
        validate_password("short")
    with pytest.raises(ValueError, match="password_too_long"):
        validate_password("x" * 129)
    validate_password("exactly08")
    # Never truncated: over-long input is rejected, not silently cut.
    assert len("x" * 129) > 128


def test_hash_roundtrip_and_fail_closed():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("secret123", "not-a-hash")


def test_register_login_logout_flow(client):
    res = _register(client)
    assert res.status_code == 201
    token = res.json()["access_token"]
    assert token

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "KID@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "kid@example.com"

    logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 204


def test_register_duplicate_email_case_insensitive(client):
    assert _register(client, email="Kid@Example.com").status_code == 201
    dup = _register(client, email="kid@example.com")
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "EMAIL_TAKEN"


def test_register_short_password_rejected(client):
    res = _register(client, email="new@example.com", password="short")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


def test_login_failures_are_generic(client):
    _register(client)
    wrong_pass = client.post(
        "/api/v1/auth/login", json={"email": "kid@example.com", "password": "nope-nope-nope"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "secret123"}
    )
    assert wrong_pass.status_code == 401
    assert unknown.status_code == 401
    assert wrong_pass.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_auth(client):
    res = client.get("/api/v1/users/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTH_REQUIRED"


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(per_minute=2, clock=lambda: now[0])
    assert limiter.allow("ip")
    assert limiter.allow("ip")
    assert not limiter.allow("ip")
    now[0] += 61.0
    assert limiter.allow("ip")


def test_auth_endpoints_rate_limited(client, monkeypatch):
    import app.core.rate_limit as rate_limit_mod

    monkeypatch.setattr(rate_limit_mod, "auth_limiter", RateLimiter(per_minute=1))
    assert _register(client, email="one@example.com").status_code == 201
    limited = _register(client, email="two@example.com")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
