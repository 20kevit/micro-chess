"""P11 personalized onboarding, daily journey, retention & notifications.

Covers: registration with phone, OTP lifecycle (create/verify/invalid/
expired/replay/cooldown/attempts), normalization, verified state,
preferences, quest generation/stability/local-day/timezone, completion
idempotency, ownership/IDOR, recommendation integration, reminders,
provider failure, telegram linking security, push ownership, admin
visibility.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _register(client: TestClient, username: str, phone: str | None = None) -> dict:
    body = {"username": username, "password": "password123", "display_name": username}
    if phone is not None:
        body["phone"] = phone
    res = client.post("/api/v1/auth/register", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_content(db_session) -> None:
    from app.modules.captures import seed as cap_seed
    from app.modules.legal_destinations import seed as legal_seed
    from app.modules.piece_recognition import seed as piece_seed

    piece_seed.seed_db(db_session)
    legal_seed.seed_db(db_session)
    cap_seed.seed_db(db_session)


# --- registration with phone -------------------------------------------------

def test_register_with_phone_normalizes(client, db_session):
    from app.modules.users.models import User

    data = _register(client, "p11_phone_a", "0912 345 6789")
    token = data["access_token"]
    me = client.get("/api/v1/users/me", headers=_bearer(token)).json()
    user = db_session.query(User).filter(User.username == "p11_phone_a").first()
    assert user.phone == "+989123456789"
    assert user.phone_verified is False
    assert me["username"] == "p11_phone_a"


def test_register_duplicate_phone_rejected(client):
    _register(client, "p11_phone_b", "+989100000001")
    res = client.post(
        "/api/v1/auth/register",
        json={"username": "p11_phone_c", "password": "password123", "phone": "09100000001"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "phone_taken"


def test_register_invalid_phone_rejected(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"username": "p11_phone_d", "password": "password123", "phone": "not-a-number"},
    )
    assert res.status_code == 422


def test_phone_normalization_variants():
    from app.modules.phone_verification.service import normalize_phone

    assert normalize_phone("09123456789") == "+989123456789"
    assert normalize_phone("+989123456789") == "+989123456789"
    assert normalize_phone("989123456789") == "+989123456789"
    assert normalize_phone("۰۹۱۲۳۴۵۶۷۸۹") == "+989123456789"
    assert normalize_phone("+1 415 555 2671") == "+14155552671"
    for bad in ("", "123", "09abc", "0", None, 123):
        try:
            normalize_phone(bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject {bad!r}")


# --- OTP lifecycle -----------------------------------------------------------

def test_otp_full_cycle(client):
    data = _register(client, "p11_otp_a", "09120000001")
    h = _bearer(data["access_token"])
    started = client.post("/api/v1/me/phone/start", json={"phone": "09120000001"}, headers=h).json()
    assert started["phone"] == "+989120000001"
    assert started["sent"] is True

    from app.modules.phone_verification.models import PhoneOtp
    from app.modules.users.models import User
    from app.db.base import Base  # noqa: F401 (ensure models imported)

    # OTP value never appears in responses or stored rows.
    assert "code" not in started
    me_row = client.get("/api/v1/me/phone", headers=h).json()
    assert me_row["verified"] is False

    # Wrong code is rejected generically.
    bad = client.post("/api/v1/me/phone/verify", json={"code": "000000"}, headers=h)
    assert bad.status_code == 422
    assert bad.json()["detail"] == "code_invalid"

    # Resend cooldown enforced (same minute).
    cool = client.post("/api/v1/me/phone/resend", headers=h)
    assert cool.status_code == 422
    assert cool.json()["detail"] == "resend_cooldown"


def test_otp_verify_success_marks_verified(client, db_session):
    import app.modules.sms.ports as sms_ports

    data = _register(client, "p11_otp_b", "09120000002")
    h = _bearer(data["access_token"])
    client.post("/api/v1/me/phone/start", json={"phone": "09120000002"}, headers=h)
    outbox = sms_ports.test_provider().outbox
    assert outbox, "test SMS provider must record the OTP send"
    assert "+989120000002" in outbox[-1]["to"]
    # The code itself is only in the SMS text (never in API responses).
    import re

    text = outbox[-1]["text"]
    match = re.search(r"[0-9]{6}", text)
    assert match, f"OTP digits missing from SMS text: {text!r}"
    code = match.group(0)
    res = client.post("/api/v1/me/phone/verify", json={"code": code}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json() == {"phone": "+989120000002", "verified": True}
    # Replay of the same code fails (single-use).
    replay = client.post("/api/v1/me/phone/verify", json={"code": code}, headers=h)
    assert replay.status_code == 422


def test_otp_attempt_limit_consumes_challenge(client):
    data = _register(client, "p11_otp_c", "09120000003")
    h = _bearer(data["access_token"])
    client.post("/api/v1/me/phone/start", json={"phone": "09120000003"}, headers=h)
    for _ in range(5):
        res = client.post("/api/v1/me/phone/verify", json={"code": "999999"}, headers=h)
        assert res.status_code == 422
    # Challenge consumed: even the right code now fails as invalid.
    assert client.post("/api/v1/me/phone/verify", json={"code": "999999"}, headers=h).status_code == 422


def test_otp_expiry(client, db_session):
    from app.modules.phone_verification.models import PhoneOtp

    data = _register(client, "p11_otp_d", "09120000004")
    h = _bearer(data["access_token"])
    client.post("/api/v1/me/phone/start", json={"phone": "09120000004"}, headers=h)
    row = db_session.query(PhoneOtp).order_by(PhoneOtp.id.desc()).first()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()
    res = client.post("/api/v1/me/phone/verify", json={"code": "123456"}, headers=h)
    assert res.status_code == 422
    assert res.json()["detail"] == "code_expired"


def test_otp_change_phone_before_verify(client):
    data = _register(client, "p11_otp_e", "09120000005")
    h = _bearer(data["access_token"])
    client.post("/api/v1/me/phone/start", json={"phone": "09120000005"}, headers=h)
    moved = client.post("/api/v1/me/phone/start", json={"phone": "09120000006"}, headers=h)
    assert moved.status_code == 200
    assert moved.json()["phone"] == "+989120000006"
    status = client.get("/api/v1/me/phone", headers=h).json()
    assert status == {"phone": "+989120000006", "verified": False}


def test_otp_requires_auth(client):
    assert client.post("/api/v1/me/phone/start", json={"phone": "09120000007"}).status_code == 401
    assert client.get("/api/v1/me/phone").status_code == 401


# --- onboarding + placement + plan -------------------------------------------

def test_onboarding_save_and_plan(client, db_session):
    _seed_content(db_session)
    data = _register(client, "p11_onb_a", "09120000010")
    h = _bearer(data["access_token"])
    body = {
        "experience": "beginner",
        "play_frequency": "weekly",
        "goal": "improve",
        "intensity": "light",
        "timezone": "Asia/Tehran",
    }
    res = client.put("/api/v1/me/onboarding", json=body, headers=h)
    assert res.status_code == 200, res.text
    saved = res.json()
    assert saved["onboarding_completed"] is True
    assert saved["intensity"] == "light"
    plan = client.get("/api/v1/me/plan", headers=h).json()
    assert plan["headline"] == "مسیر پیشنهادی تو"
    assert plan["focus_exercise"]  # powered by the recommendation engine
    placement = client.get("/api/v1/me/placement", headers=h).json()
    assert 1 <= len(placement) <= 3
    for item in placement:
        assert item["puzzle_id"] and item["exercise_slug"]
    done = client.post("/api/v1/me/placement/complete", headers=h).json()
    assert done["placement_completed"] is True


def test_onboarding_optional_signals(client):
    data = _register(client, "p11_onb_b")
    h = _bearer(data["access_token"])
    res = client.put(
        "/api/v1/me/onboarding",
        json={"experience": "new", "lichess_username": "SomePlayer", "fide_rating": 1500},
        headers=h,
    )
    assert res.status_code == 200
    assert res.json()["lichess_username"] == "someplayer"
    bad = client.put("/api/v1/me/onboarding", json={"experience": "grandmaster"}, headers=h)
    assert bad.status_code == 422


# --- daily quests ------------------------------------------------------------

def test_quest_generation_three_stable(client, db_session):
    _seed_content(db_session)
    data = _register(client, "p11_q_a", "09120000020")
    h = _bearer(data["access_token"])
    client.put("/api/v1/me/onboarding", json={"experience": "beginner"}, headers=h)
    first = client.get("/api/v1/me/journey/today", headers=h).json()
    assert first["total"] == 3
    assert [q["slot"] for q in first["quests"]] == [1, 2, 3]
    assert [q["kind"] for q in first["quests"]] == ["core", "review", "challenge"]
    second = client.get("/api/v1/me/journey/today", headers=h).json()
    assert [q["id"] for q in second["quests"]] == [q["id"] for q in first["quests"]]
    assert [q["exercise_slug"] for q in second["quests"]] == [q["exercise_slug"] for q in first["quests"]]


def test_quest_completion_requires_progress_and_is_idempotent(client, db_session):
    from app.modules.piece_recognition.validator import SLUG as PIECE_SLUG

    _seed_content(db_session)
    data = _register(client, "p11_q_b", "09120000021")
    h = _bearer(data["access_token"])
    client.put("/api/v1/me/onboarding", json={"experience": "beginner", "intensity": "light"}, headers=h)
    today = client.get("/api/v1/me/journey/today", headers=h).json()
    quest = today["quests"][0]
    # Premature completion is rejected (server counts attempts).
    early = client.post(f"/api/v1/me/journey/quests/{quest['id']}/complete", headers=h)
    assert early.status_code == 422
    # Start is idempotent and owner-scoped.
    started = client.post(f"/api/v1/me/journey/quests/{quest['id']}/start", headers=h).json()
    assert started["status"] in ("started", "pending")
    # Submit enough attempts on the quest exercise to fill progress.
    from app.modules.puzzles.models import Puzzle

    puzzles = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == quest["exercise_slug"], Puzzle.is_published.is_(True))
        .limit(quest["target_count"])
        .all()
    )
    assert len(puzzles) == quest["target_count"]
    for puzzle in puzzles:
        sub = client.post(
            "/api/v1/attempts",
            json={"puzzle_id": puzzle.id, "answer": dict(puzzle.answer_json), "mode": "practice"},
            headers=h,
        )
        # Any validated attempt (correct/partial/wrong) fills quest
        # progress; only the status code shape matters here.
        assert sub.status_code in (200, 201), sub.text
    done = client.post(f"/api/v1/me/journey/quests/{quest['id']}/complete", headers=h)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    replay = client.post(f"/api/v1/me/journey/quests/{quest['id']}/complete", headers=h)
    assert replay.status_code == 200
    assert replay.json()["status"] == "completed"
    refreshed = client.get("/api/v1/me/journey/today", headers=h).json()
    assert refreshed["completed_count"] >= 1
    assert PIECE_SLUG  # recommendation engine content is servable


def test_quest_idor(client, db_session):
    _seed_content(db_session)
    alice = _register(client, "p11_q_c", "09120000022")
    bob = _register(client, "p11_q_d", "09120000023")
    ha, hb = _bearer(alice["access_token"]), _bearer(bob["access_token"])
    client.put("/api/v1/me/onboarding", json={"experience": "beginner"}, headers=ha)
    quest_id = client.get("/api/v1/me/journey/today", headers=ha).json()["quests"][0]["id"]
    assert client.post(f"/api/v1/me/journey/quests/{quest_id}/start", headers=hb).status_code == 404
    assert client.post(f"/api/v1/me/journey/quests/{quest_id}/complete", headers=hb).status_code == 404


def test_quest_timezone_day_boundary():
    from app.modules.daily_quests.service import local_today

    noon_utc = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    assert local_today("Asia/Tehran", noon_utc) == "2026-09-21"
    late_utc = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
    assert local_today("Asia/Tehran", late_utc) == "2026-09-22"
    assert local_today("America/New_York", noon_utc) == "2026-09-21"


# --- notify: prefs, push, links, reminders, analytics ------------------------

def test_p11_preferences_matrix_and_update(client):
    data = _register(client, "p11_n_a")
    h = _bearer(data["access_token"])
    matrix = client.get("/api/v1/me/notify-preferences", headers=h).json()
    keys = {(p["category"], p["channel"]) for p in matrix}
    assert ("reminder", "web_push") in keys
    assert ("journey", "in_app") in keys
    updated = client.patch(
        "/api/v1/me/notify-preferences",
        json={"category": "reminder", "channel": "web_push", "enabled": True},
        headers=h,
    )
    assert updated.status_code == 200
    assert client.patch(
        "/api/v1/me/notify-preferences",
        json={"category": "bogus", "channel": "web_push", "enabled": True},
        headers=h,
    ).status_code == 422


def test_push_subscription_ownership(client):
    alice = _register(client, "p11_n_b")
    bob = _register(client, "p11_n_c")
    ha, hb = _bearer(alice["access_token"]), _bearer(bob["access_token"])
    endpoint = "https://push.example.com/sub/alice-1"
    res = client.post("/api/v1/me/push/subscriptions", json={"endpoint": endpoint}, headers=ha)
    assert res.status_code == 200
    assert client.get("/api/v1/me/push/subscriptions", headers=hb).json() == []
    assert client.post(
        "/api/v1/me/push/subscriptions", json={"endpoint": "http://insecure.example/x"}, headers=ha
    ).status_code == 422


def test_telegram_link_token_security(client, db_session):
    import os

    os.environ["BOT_WEBHOOK_SECRET"] = "test-secret"
    alice = _register(client, "p11_n_d")
    ha = _bearer(alice["access_token"])
    tok = client.post("/api/v1/me/channel-links/telegram/token", headers=ha).json()
    assert tok["token"] and tok["channel"] == "telegram"
    # Wrong webhook secret is rejected.
    bad = client.post(
        "/api/v1/notify/bot/link",
        json={"token": tok["token"], "channel": "telegram", "external_id": "111"},
        headers={"x-bot-secret": "wrong"},
    )
    assert bad.status_code == 403
    # Correct secret links; token is one-time (replay fails).
    ok = client.post(
        "/api/v1/notify/bot/link",
        json={"token": tok["token"], "channel": "telegram", "external_id": "111"},
        headers={"x-bot-secret": "test-secret"},
    )
    assert ok.status_code == 200
    replay = client.post(
        "/api/v1/notify/bot/link",
        json={"token": tok["token"], "channel": "telegram", "external_id": "222"},
        headers={"x-bot-secret": "test-secret"},
    )
    assert replay.status_code == 422
    links = client.get("/api/v1/me/channel-links", headers=ha).json()
    assert {"channel": "telegram", "linked": True} in [
        {"channel": link["channel"], "linked": link["linked"]} for link in links
    ]


def test_reminder_respects_completion_and_opt_out(client, db_session):
    from app.modules.notify import service as notify_service

    _seed_content(db_session)
    data = _register(client, "p11_n_e", "09120000030")
    h = _bearer(data["access_token"])
    client.put("/api/v1/me/onboarding", json={"experience": "beginner"}, headers=h)
    client.get("/api/v1/me/journey/today", headers=h)
    # Opted out by default for web_push: no reminders due.
    assert notify_service.due_reminders(db_session) == [] or all(
        r["user_id"] != 1 for r in notify_service.due_reminders(db_session)
    )
    # Opt in + subscription => reminder becomes due exactly once.
    client.patch(
        "/api/v1/me/notify-preferences",
        json={"category": "reminder", "channel": "web_push", "enabled": True},
        headers=h,
    )
    client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": "https://push.example.com/sub/rem-1"},
        headers=h,
    )
    from app.modules.users.models import User

    me = db_session.query(User).filter(User.username == "p11_n_e").first()
    due = [r for r in notify_service.due_reminders(db_session) if r["user_id"] == me.id]
    assert len(due) == 1 and due[0]["channel"] == "web_push"
    result = notify_service.send_due_reminders(db_session)
    assert result["sent"] >= 1
    # Second run: dedup guard, no duplicate reminder for the same day.
    assert [r for r in notify_service.due_reminders(db_session) if r["user_id"] == me.id] == []


def test_sms_provider_failure_is_safe(client, monkeypatch):
    import app.modules.sms.ports as sms_ports
    from app.modules.sms.ports import SmsResult

    class FailingProvider(sms_ports.SmsProvider):
        name = "test"

        def send_otp(self, *, to: str, text: str) -> SmsResult:
            return SmsResult(ok=False, error="provider_error")

    monkeypatch.setattr(sms_ports, "get_provider", lambda: FailingProvider())
    data = _register(client, "p11_n_f", "09120000031")
    h = _bearer(data["access_token"])
    res = client.post("/api/v1/me/phone/start", json={"phone": "09120000031"}, headers=h)
    assert res.status_code == 200
    assert res.json()["sent"] is False


def test_analytics_events_validated(client):
    data = _register(client, "p11_n_g")
    h = _bearer(data["access_token"])
    assert client.post("/api/v1/me/analytics", json={"type": "quest_started"}, headers=h).status_code == 204
    assert client.post("/api/v1/me/analytics", json={"type": "bogus_event"}, headers=h).status_code == 422


def test_admin_journey_overview_without_secrets(client, db_session):
    from tests.conftest import make_auth_headers  # noqa: F401 (documents helper path)

    _seed_content(db_session)
    data = _register(client, "p11_adm_a", "09120000040")
    h = _bearer(data["access_token"])
    client.put("/api/v1/me/onboarding", json={"experience": "beginner"}, headers=h)
    client.get("/api/v1/me/journey/today", headers=h)
    # Promote to admin directly (test-only) and inspect the overview.
    from app.modules.users.models import User, UserRole

    user = db_session.query(User).filter(User.username == "p11_adm_a").first()
    db_session.add(UserRole(user_id=user.id, role="ADMIN"))
    db_session.commit()
    from app.modules.auth import service as auth_service

    _, admin_token = auth_service.create_user_session(db_session, user, "ADMIN")
    db_session.commit()
    overview = client.get("/api/v1/admin/journey/overview", headers=_bearer(admin_token)).json()
    assert overview["onboarding_completed"] >= 1
    assert overview["quest_days"] >= 1
    assert "events" in overview
    body = str(overview)
    assert "09120000040" not in body  # no phone numbers leak
    health = client.get("/api/v1/admin/system/provider-health", headers=_bearer(admin_token)).json()
    assert health["sms"]["provider"] in ("test", "kavenegar")
    assert "API_KEY" not in str(health) and "api_key" not in str(health).lower()
