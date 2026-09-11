"""Foundation: configuration, request-id propagation, audit hygiene."""

import logging

import pytest

from app.core.audit import audit_event
from app.core.config import Settings


def test_dev_defaults_are_usable():
    settings = Settings()
    assert settings.jwt_expire_minutes == 60
    assert "http://localhost:5173" in settings.cors_origins
    assert settings.rate_limit_enabled is True
    assert settings.auth_rate_limit_per_minute > 0
    # Development must start without extra secrets.
    settings.ensure_ready()


def test_production_refuses_default_secret():
    settings = Settings(environment="production", jwt_secret="change-me-in-production")
    with pytest.raises(RuntimeError):
        settings.ensure_ready()


def test_production_accepts_unique_secret():
    settings = Settings(environment="production", jwt_secret="a-unique-secret-value-here")
    settings.ensure_ready()


def test_responses_carry_request_id(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Request-ID"]


def test_request_id_is_propagated_when_provided(client):
    res = client.get("/health", headers={"X-Request-ID": "probe123"})
    assert res.headers["X-Request-ID"] == "probe123"


def test_audit_event_logs_without_secrets(caplog):
    with caplog.at_level(logging.INFO, logger="microchess.audit"):
        audit_event(action="auth.login", actor=7, result="failed")
    assert "auth.login" in caplog.text
    assert "password" not in caplog.text
    assert "token" not in caplog.text
