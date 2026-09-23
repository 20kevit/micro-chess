"""Telegram/Bale phone verification: sessions, pairing codes, contacts.

Sessions are one-time, user-bound, short-lived. Contacts must satisfy
the provider ownership proof (contact.user_id == sender id). Phones
verified on another account are rejected without leaking that
account. Webhook is secret-guarded and idempotent.
"""

import os
from datetime import datetime, timezone

import pytest
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


def _user_id(db_session, username: str) -> int:
    from app.modules.users.models import User

    return int(db_session.query(User).filter(User.username == username).first().id)


@pytest.fixture()
def webhook_secret(monkeypatch):
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", "test-hook-secret")
    yield "test-hook-secret"


@pytest.fixture()
def fake_bots():
    from app.modules.verification import bots

    telegram = bots.FakeBotAdapter(channel="telegram")
    bale = bots.FakeBotAdapter(channel="bale")
    bots.set_adapter(telegram)
    bots.set_adapter(bale)
    yield {"telegram": telegram, "bale": bale}
    bots.clear_adapters()


def _session(client, headers, channel="telegram"):
    res = client.post("/api/v1/me/verification/sessions",
                      json={"channel": channel}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _webhook(client, channel, update, secret="test-hook-secret"):
    return client.post(f"/api/v1/verification/webhook/{channel}", json=update,
                       headers={"x-bot-secret": secret})


def _contact_update(chat_id, sender_id, contact_user_id, phone, name="Ali"):
    return {"message": {"chat": {"id": chat_id}, "from": {"id": sender_id},
                        "contact": {"user_id": contact_user_id, "phone_number": phone,
                                    "first_name": name}}}


# --- sessions ------------------------------------------------------------------

def test_normalization_variants():
    from app.modules.verification.service import normalize_phone

    assert normalize_phone("09123456789") == "+989123456789"
    assert normalize_phone("+989123456789") == "+989123456789"
    assert normalize_phone("989123456789") == "+989123456789"
    assert normalize_phone("۰۹۱۲۳۴۵۶۷۸۹") == "+989123456789"
    for bad in ("", "123", "09abc", None, 123):
        try:
            normalize_phone(bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject {bad!r}")


@pytest.mark.parametrize("channel", ["telegram", "bale"])
def test_session_create_and_status(client, channel):
    h = _bearer(_register(client, f"v_sess_{channel}")["access_token"])
    body = _session(client, h, channel)
    assert len(body["pairing_code"]) == 6 and body["pairing_code"].isdigit()
    assert "token" not in body  # internal token never leaves the server
    assert body["channel"] == channel
    status = client.get("/api/v1/me/verification/status", headers=h).json()
    assert status == {"verified": False, "phone_masked": "", "channel": None}


def test_session_unknown_channel_and_auth(client):
    h = _bearer(_register(client, "v_sess_bad")["access_token"])
    assert client.post("/api/v1/me/verification/sessions",
                       json={"channel": "sms"}, headers=h).status_code == 422
    assert client.post("/api/v1/me/verification/sessions",
                       json={"channel": "telegram"}).status_code == 401


def test_already_verified_cannot_create_session(client, db_session):
    data = _register(client, "v_sess_done")
    h = _bearer(data["access_token"])
    from app.modules.users.models import User

    user = db_session.get(User, _user_id(db_session, "v_sess_done"))
    user.phone = "+989100000010"
    user.phone_verified = True
    db_session.commit()
    assert client.post("/api/v1/me/verification/sessions",
                       json={"channel": "telegram"}, headers=h).status_code == 409


def test_two_tabs_second_session_invalidates_first(client, db_session):
    from app.modules.notify.models import ChannelLinkToken

    h = _bearer(_register(client, "v_tabs")["access_token"])
    first = _session(client, h)["pairing_code"]
    second = _session(client, h)["pairing_code"]
    assert first != second
    live = db_session.query(ChannelLinkToken).filter(
        ChannelLinkToken.used_at.is_(None)).all()
    assert len(live) == 1 and live[0].pairing_code == second


# --- webhook: pairing + contact --------------------------------------------------

@pytest.mark.parametrize("channel", ["telegram", "bale"])
def test_full_flow_pairing_then_contact(client, db_session, webhook_secret, fake_bots, channel):
    data = _register(client, f"v_full_{channel}")
    h = _bearer(data["access_token"])
    code = _session(client, h, channel)["pairing_code"]
    bot = fake_bots[channel]

    assert _webhook(client, channel, {"message": {"chat": {"id": 111},
                                                 "text": "/start"}}).status_code == 200
    assert "کد" in bot.outbox[-1]["text"]

    assert _webhook(client, channel, {"message": {"chat": {"id": 111},
                                                 "text": code}}).status_code == 200
    asked = bot.outbox[-1]
    assert asked["reply_markup"]["keyboard"][0][0]["request_contact"] is True

    assert _webhook(client, channel,
                    _contact_update(111, 777, 777, "09120000001")).status_code == 200
    assert "تأیید شد" in bot.outbox[-1]["text"]
    assert bot.outbox[-1]["reply_markup"] == {"remove_keyboard": True}

    from app.modules.player.models import PlayerExternalIdentity
    from app.modules.users.models import User

    user = db_session.get(User, _user_id(db_session, f"v_full_{channel}"))
    assert user.phone == "+989120000001" and user.phone_verified is True
    identity = db_session.query(PlayerExternalIdentity).filter(
        PlayerExternalIdentity.user_id == user.id,
        PlayerExternalIdentity.provider == channel).first()
    assert identity is not None and identity.is_verified is True
    assert identity.provider_user_id == "777"
    status = client.get("/api/v1/me/verification/status", headers=h).json()
    assert status["verified"] is True and status["channel"] == channel
    assert status["phone_masked"] != "" and "9120000001" not in status["phone_masked"]


def test_contact_from_another_person_rejected(client, db_session, webhook_secret, fake_bots):
    data = _register(client, "v_stranger")
    h = _bearer(data["access_token"])
    code = _session(client, h)["pairing_code"]
    bot = fake_bots["telegram"]
    _webhook(client, "telegram", {"message": {"chat": {"id": 111}, "text": code}})
    # contact.user_id (888) != sender id (777): someone else's contact.
    assert _webhook(client, "telegram",
                    _contact_update(111, 777, 888, "09120000002")).status_code == 200
    assert "قابل تأیید نیست" in bot.outbox[-1]["text"]
    from app.modules.users.models import User

    user = db_session.get(User, _user_id(db_session, "v_stranger"))
    assert user.phone_verified is False and user.phone is None


def test_duplicate_phone_rejected_without_leak(client, db_session, webhook_secret, fake_bots):
    from app.modules.users.models import User

    alice = _register(client, "v_dup_a")
    other = db_session.get(User, _user_id(db_session, "v_dup_a"))
    other.phone = "+989120000003"
    other.phone_verified = True
    db_session.commit()
    _ = alice

    data = _register(client, "v_dup_b")
    h = _bearer(data["access_token"])
    code = _session(client, h)["pairing_code"]
    bot = fake_bots["telegram"]
    _webhook(client, "telegram", {"message": {"chat": {"id": 222}, "text": code}})
    res = _webhook(client, "telegram", _contact_update(222, 555, 555, "09120000003"))
    assert res.status_code == 200
    assert "قبلاً برای یک حساب دیگر" in bot.outbox[-1]["text"]
    # No leak: other account's username appears nowhere.
    assert "v_dup_a" not in str(bot.outbox)
    me = db_session.get(User, _user_id(db_session, "v_dup_b"))
    assert me.phone_verified is False


def test_identity_takeover_rejected(client, db_session, webhook_secret, fake_bots):
    from app.modules.player.models import PlayerExternalIdentity
    from app.modules.users.models import User

    data = _register(client, "v_take_a")
    alice_id = _user_id(db_session, "v_take_a")
    alice = db_session.get(User, alice_id)
    alice.phone = "+989120000004"
    alice.phone_verified = True
    db_session.add(PlayerExternalIdentity(
        user_id=alice_id, provider="telegram", external_username="666",
        provider_user_id="666", is_verified=True,
        verified_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db_session.commit()
    _ = data

    data = _register(client, "v_take_b")
    h = _bearer(data["access_token"])
    code = _session(client, h)["pairing_code"]
    _webhook(client, "telegram", {"message": {"chat": {"id": 333}, "text": code}})
    # Same platform id 666, fresh number: still rejected (stable-id binding).
    res = _webhook(client, "telegram", _contact_update(333, 666, 666, "09120000005"))
    assert res.status_code == 200
    me = db_session.get(User, _user_id(db_session, "v_take_b"))
    assert me.phone_verified is False


def test_expired_and_reused_sessions(client, db_session, webhook_secret, fake_bots):
    from datetime import timedelta

    from app.modules.notify.models import ChannelLinkToken

    data = _register(client, "v_exp")
    h = _bearer(data["access_token"])
    code = _session(client, h)["pairing_code"]
    row = db_session.query(ChannelLinkToken).filter(
        ChannelLinkToken.pairing_code == code).first()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()
    bot = fake_bots["telegram"]
    _webhook(client, "telegram", {"message": {"chat": {"id": 444}, "text": code}})
    assert "منقضی" in bot.outbox[-1]["text"]
    # Consumed session cannot be reused afterwards either.
    code2 = _session(client, h)["pairing_code"]
    _webhook(client, "telegram", {"message": {"chat": {"id": 444}, "text": code2}})
    _webhook(client, "telegram", _contact_update(444, 101, 101, "09120000006"))
    replay = _webhook(client, "telegram", _contact_update(444, 101, 101, "09120000006"))
    assert replay.status_code == 200  # fail closed, provider-safe 200
    from app.modules.users.models import User

    me = db_session.get(User, _user_id(db_session, "v_exp"))
    assert me.phone == "+989120000006"  # first (valid) verification stands


def test_webhook_auth_and_malformed(client, webhook_secret, fake_bots):
    assert client.post("/api/v1/verification/webhook/telegram",
                       json={}, headers={"x-bot-secret": "wrong"}).status_code == 403
    assert client.post("/api/v1/verification/webhook/sms",
                       json={}, headers={"x-bot-secret": webhook_secret}).status_code == 404
    # Malformed updates answer 200 without leaking anything.
    assert client.post("/api/v1/verification/webhook/telegram", json={"bogus": 1},
                       headers={"x-bot-secret": webhook_secret}).status_code == 200
    assert client.post("/api/v1/verification/webhook/telegram", json={},
                       headers={"x-bot-secret": webhook_secret}).status_code == 200


def test_provider_send_failure_still_verifies(client, db_session, webhook_secret):
    from app.modules.verification import bots
    from app.modules.verification.bots import BotResult

    class SilentBots(bots.BotAdapter):
        channel = "telegram"

        def send_text(self, chat_id, text, reply_markup=None):
            return BotResult(ok=False, error="send_failed")

        def get_me(self):
            return {"id": 9, "username": "t"}

    bots.set_adapter(SilentBots())
    try:
        data = _register(client, "v_silent")
        h = _bearer(data["access_token"])
        code = _session(client, h)["pairing_code"]
        _webhook(client, "telegram", {"message": {"chat": {"id": 555}, "text": code}})
        assert _webhook(client, "telegram",
                        _contact_update(555, 202, 202, "09120000007")).status_code == 200
        from app.modules.users.models import User

        me = db_session.get(User, _user_id(db_session, "v_silent"))
        assert me.phone_verified is True
    finally:
        bots.clear_adapters()


def test_logout_during_verification_keeps_session(client, db_session, webhook_secret, fake_bots):
    data = _register(client, "v_logout")
    h = _bearer(data["access_token"])
    code = _session(client, h)["pairing_code"]
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    # The pending session is bound to the user id, not the MicroChess
    # session: verification completes after logout.
    _webhook(client, "telegram", {"message": {"chat": {"id": 666}, "text": code}})
    _webhook(client, "telegram", _contact_update(666, 303, 303, "09120000008"))
    from app.modules.users.models import User

    me = db_session.get(User, _user_id(db_session, "v_logout"))
    assert me.phone == "+989120000008" and me.phone_verified is True


def test_verification_survives_login_and_preserves_state(client, db_session):
    from app.modules.users.models import User

    data = _register(client, "v_login")
    me = db_session.get(User, _user_id(db_session, "v_login"))
    me.phone = "+989120000009"
    me.phone_verified = True
    db_session.commit()
    login = client.post("/api/v1/auth/login",
                        json={"username": "v_login", "password": "password123"})
    assert login.status_code == 200
    status = client.get("/api/v1/me/verification/status",
                        headers=_bearer(login.json()["access_token"])).json()
    assert status["verified"] is True
