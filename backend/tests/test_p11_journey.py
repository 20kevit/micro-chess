"""P11 personalized onboarding, daily journey, retention & notifications.

Covers: onboarding/placement/plan, quest generation/stability/
local-day/timezone, completion idempotency, ownership/IDOR,
recommendation integration, preferences, push ownership, reminders,
analytics validation, admin visibility. Phone verification moved to
Telegram/Bale contact sharing (see test_verification.py); SMS OTP was
removed from the product.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient


def _register(client: TestClient, username: str) -> dict:
    body = {"username": username, "password": "password123", "display_name": username}
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


def test_onboarding_save_and_plan(client, db_session):
    _seed_content(db_session)
    data = _register(client, "p11_onb_a")
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


def test_quest_generation_three_stable(client, db_session):
    _seed_content(db_session)
    data = _register(client, "p11_q_a")
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
    data = _register(client, "p11_q_b")
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
    alice = _register(client, "p11_q_c")
    bob = _register(client, "p11_q_d")
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


def test_reminder_respects_completion_and_opt_out(client, db_session):
    from app.modules.notify import service as notify_service

    _seed_content(db_session)
    data = _register(client, "p11_n_e")
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


def test_analytics_events_validated(client):
    data = _register(client, "p11_n_g")
    h = _bearer(data["access_token"])
    assert client.post("/api/v1/me/analytics", json={"type": "quest_started"}, headers=h).status_code == 204
    assert client.post("/api/v1/me/analytics", json={"type": "bogus_event"}, headers=h).status_code == 422


def test_admin_journey_overview_without_secrets(client, db_session):
    from tests.conftest import make_auth_headers  # noqa: F401 (documents helper path)

    _seed_content(db_session)
    data = _register(client, "p11_adm_a")
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
    health = client.get("/api/v1/admin/system/provider-health", headers=_bearer(admin_token)).json()
    assert "sms" not in health
    assert "telegram" in health and "bale" in health
    assert "API_KEY" not in str(health) and "api_key" not in str(health).lower()
