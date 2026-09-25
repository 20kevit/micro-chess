from datetime import datetime, timedelta, timezone

from app.modules.admin.models import AuditLog
from app.modules.billing import service as billing
from app.modules.exercises.models import Exercise
from app.modules.player.models import PlayerExternalIdentity
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import (
    Puzzle,
    PuzzleReview,
    PuzzleStatusHistory,
    PuzzleValidation,
)
from app.modules.users.models import User, UserRole


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(client, db_session, username="p13_admin"):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 201, response.text
    user = db_session.query(User).filter(User.username == username).one()
    db_session.add(UserRole(user_id=user.id, role="ADMIN"))
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123", "role": "ADMIN"},
    )
    assert login.status_code == 200, login.text
    return _bearer(login.json()["access_token"])


def _exercise(db_session, slug="pin"):
    row = db_session.get(Exercise, slug)
    if row is None:
        row = Exercise(slug=slug, title_fa="آچمز", is_active=True, sort_order=1)
        db_session.add(row)
        db_session.commit()
    return row


def _draft(client, headers, **fields):
    body = {
        "exercise_slug": "pin",
        "answer_json": {"moves": ["e2e4"]},
        "prompt_fa": "سوال",
    }
    body.update(fields)
    response = client.post("/api/v1/admin/puzzles", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_manual_draft_hard_delete_is_audited_and_history_is_blocked(client, db_session):
    headers = _admin_headers(client, db_session)
    _exercise(db_session)
    deletable = _draft(client, headers)
    response = client.delete(f"/api/v1/admin/puzzles/{deletable['id']}", headers=headers)
    assert response.status_code == 204, response.text
    assert db_session.get(Puzzle, deletable["id"]) is None
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "puzzles.delete", AuditLog.target_id == str(deletable["id"]))
        .one()
    )
    assert audit.actor_user_id is not None
    assert "answer" not in str(audit.metadata_json).lower()

    blocked = _draft(client, headers)
    db_session.add(
        Attempt(
            user_id=1,
            puzzle_id=blocked["id"],
            exercise_slug="pin",
            mode="practice",
            result="wrong",
            answer_json={},
        )
    )
    db_session.commit()
    response = client.delete(f"/api/v1/admin/puzzles/{blocked['id']}", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PUZZLE_DELETE_CONFLICT"
    assert db_session.get(Puzzle, blocked["id"]) is not None

    history_blocked = _draft(client, headers)
    db_session.add(
        PuzzleStatusHistory(
            puzzle_id=history_blocked["id"],
            from_status="draft",
            to_status="validated",
            changed_by_user_id=None,
        )
    )
    db_session.commit()
    assert client.delete(
        f"/api/v1/admin/puzzles/{history_blocked['id']}", headers=headers
    ).status_code == 409

    validation_blocked = _draft(client, headers)
    db_session.add(
        PuzzleValidation(
            puzzle_id=validation_blocked["id"],
            status="pass",
            result_json={},
        )
    )
    db_session.commit()
    assert client.delete(
        f"/api/v1/admin/puzzles/{validation_blocked['id']}", headers=headers
    ).status_code == 409

    review_blocked = _draft(client, headers)
    db_session.add(
        PuzzleReview(
            puzzle_id=review_blocked["id"],
            decision="approve",
            notes="reviewed",
        )
    )
    db_session.commit()
    assert client.delete(
        f"/api/v1/admin/puzzles/{review_blocked['id']}", headers=headers
    ).status_code == 409

    generated_blocked = _draft(client, headers)
    puzzle = db_session.get(Puzzle, generated_blocked["id"])
    puzzle.source = "generated"
    puzzle.generator_run_id = 999
    db_session.commit()
    response = client.delete(
        f"/api/v1/admin/puzzles/{generated_blocked['id']}", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PUZZLE_DELETE_CONFLICT"


def test_admin_lists_keep_arrays_and_report_filtered_totals(client, db_session):
    headers = _admin_headers(client, db_session)
    _exercise(db_session)
    _draft(client, headers)
    _draft(client, headers)

    for path in (
        "/api/v1/admin/users?page_size=1",
        "/api/v1/admin/puzzles?status=draft&page_size=1",
        "/api/v1/admin/review-queue?status=approved&page_size=1",
        "/api/v1/admin/audit?page_size=1",
        "/api/v1/admin/generator-runs?page_size=1",
        "/api/v1/admin/support/tickets?page_size=1",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert isinstance(response.json(), list), path
        assert response.headers.get("X-Total-Count") is not None, path

    player = client.post(
        "/api/v1/auth/register",
        json={"username": "p13_ticket_owner", "password": "secret123"},
    ).json()["access_token"]
    ticket = client.post(
        "/api/v1/support/tickets",
        json={"subject": "help", "message": "need help", "category": "account"},
        headers=_bearer(player),
    )
    assert ticket.status_code == 201, ticket.text
    tickets = client.get("/api/v1/admin/support/tickets?category=account", headers=headers)
    assert tickets.headers["X-Total-Count"] == "1"
    assert len(tickets.json()) == 1

    run = client.post(
        "/api/v1/admin/generators/piece-recognition-v1/runs",
        json={"count": 1, "seed": 71},
        headers=headers,
    )
    assert run.status_code == 201, run.text
    runs = client.get(
        "/api/v1/admin/generator-runs?generator=piece-recognition-v1", headers=headers
    )
    assert runs.headers["X-Total-Count"] == "1"

    billing.ensure_default_plans(db_session)
    coupon = billing.create_coupon(
        db_session,
        code="P13COUNT",
        discount_type="free_trial",
        trial_days=7,
    )
    target = client.post(
        "/api/v1/auth/register",
        json={
            "username": "p13_billing_owner",
            "password": "secret123",
            "coupon_code": coupon.code,
        },
    )
    assert target.status_code == 201, target.text
    for path in (
        "/api/v1/admin/billing/redemptions?coupon_code=P13COUNT",
        "/api/v1/admin/billing/subscriptions?status=trialing",
        "/api/v1/admin/billing/payments?status=pending",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert isinstance(response.json(), list), path
        assert response.headers.get("X-Total-Count") is not None, path


def test_audit_filters_target_and_date_window_and_reports_filtered_total(client, db_session):
    headers = _admin_headers(client, db_session)
    admin = db_session.query(User).filter(User.username == "p13_admin").one()
    before = AuditLog(
        actor_user_id=admin.id,
        action="p13.audit.before",
        target_type="puzzle",
        target_id="501",
        metadata_json={},
        result="ok",
        created_at=datetime(2026, 1, 1, 23, 59, 59),
    )
    inside_start = AuditLog(
        actor_user_id=admin.id,
        action="p13.audit.start",
        target_type="puzzle",
        target_id="501",
        metadata_json={},
        result="ok",
        created_at=datetime(2026, 1, 2, 0, 0, 0),
    )
    inside_end = AuditLog(
        actor_user_id=admin.id,
        action="p13.audit.end",
        target_type="puzzle",
        target_id="501",
        metadata_json={},
        result="ok",
        created_at=datetime(2026, 1, 4, 23, 59, 59, 999999),
    )
    other_target = AuditLog(
        actor_user_id=admin.id,
        action="p13.audit.other",
        target_type="puzzle",
        target_id="502",
        metadata_json={},
        result="ok",
        created_at=datetime(2026, 1, 3, 12, 0, 0),
    )
    db_session.add_all([before, inside_start, inside_end, other_target])
    db_session.commit()

    response = client.get(
        "/api/v1/admin/audit?target_id=501&date_from=2026-01-02&date_to=2026-01-04&page_size=1",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["X-Total-Count"] == "2"
    assert len(body) == 1
    assert body[0]["id"] == inside_end.id
    assert body[0]["target_id"] == "501"


def test_audit_invalid_dates_return_422(client, db_session):
    headers = _admin_headers(client, db_session)
    for parameter, code in (
        ("date_from=2026-99-99", "INVALID_DATE_FROM"),
        ("date_to=not-a-date", "INVALID_DATE_TO"),
    ):
        response = client.get(f"/api/v1/admin/audit?{parameter}", headers=headers)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
        assert response.json()["detail"] == code.lower()


def test_review_queue_prioritizes_before_pagination_and_includes_context(client, db_session):
    headers = _admin_headers(client, db_session)
    _exercise(db_session)
    owner = client.post(
        "/api/v1/auth/register",
        json={"username": "p13_review_owner", "password": "secret123"},
    ).json()
    owner_id = db_session.query(User).filter(User.username == "p13_review_owner").one().id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    approved = Puzzle(
        exercise_slug="pin",
        answer_json={"moves": ["e2e4"]},
        position_json={},
        source="manual",
        source_reference="manual-ref",
        status="approved",
        prompt_fa="approved prompt",
        explanation="approved explanation",
        created_at=now,
    )
    quarantined = Puzzle(
        exercise_slug="pin",
        answer_json={"moves": ["d2d4"]},
        position_json={},
        source="manual",
        status="quarantined",
        prompt_fa="quarantine prompt",
        explanation="quarantine explanation",
        created_at=now - timedelta(minutes=5),
    )
    db_session.add_all([approved, quarantined])
    db_session.commit()
    db_session.add(
        PuzzleValidation(
            puzzle_id=approved.id,
            status="pass",
            result_json={},
            validated_by_user_id=owner_id,
        )
    )
    db_session.add(
        Attempt(
            user_id=owner_id,
            puzzle_id=approved.id,
            exercise_slug="pin",
            mode="practice",
            result="wrong",
            answer_json={},
        )
    )
    db_session.add(
        AuditLog(
            actor_user_id=owner_id,
            action="puzzles.create",
            target_type="puzzle",
            target_id=str(approved.id),
            metadata_json={},
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/admin/review-queue?page_size=1", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["X-Total-Count"] == "2"
    first = response.json()[0]
    assert first["id"] == quarantined.id
    assert first["severity"] == "high"
    assert first["attempts"] == 0
    assert first["usage_attempts"] == 0
    assert first["latest_validation_status"] is None

    all_rows = client.get(
        "/api/v1/admin/review-queue?page_size=50", headers=headers
    ).json()
    approved_row = next(row for row in all_rows if row["id"] == approved.id)
    assert approved_row["fen"] is None
    assert approved_row["position_json"] == {}
    assert approved_row["answer_json"] == {"moves": ["e2e4"]}
    assert approved_row["prompt_fa"] == "approved prompt"
    assert approved_row["explanation"] == "approved explanation"
    assert approved_row["source_reference"] == "manual-ref"
    assert approved_row["validation_status"] == "pass"
    assert approved_row["usage_attempts"] == 1
    assert approved_row["creator"]["user_id"] == owner_id
    assert approved_row["creator_username"] == "p13_review_owner"
    assert "phone" not in str(approved_row).lower()
    assert "token" not in str(approved_row).lower()
    _ = owner


def test_admin_user_summaries_and_profile_verification_are_safe(client, db_session):
    headers = _admin_headers(client, db_session)
    registration = client.post(
        "/api/v1/auth/register",
        json={"username": "p13_profile_user", "password": "secret123"},
    )
    assert registration.status_code == 201, registration.text
    user = db_session.query(User).filter(User.username == "p13_profile_user").one()
    user.phone = "+989121234567"
    user.phone_verified = True
    _exercise(db_session)
    puzzle = Puzzle(
        exercise_slug="pin",
        answer_json={"moves": ["e2e4"]},
        position_json={},
        source="manual",
        status="published",
        is_published=True,
    )
    db_session.add(puzzle)
    db_session.commit()
    db_session.add(
        PlayerExternalIdentity(
            user_id=user.id,
            provider="telegram",
            external_username="p13-telegram-id",
            provider_user_id="p13-telegram-id",
            is_verified=True,
        )
    )
    db_session.add(
        Attempt(
            user_id=user.id,
            puzzle_id=puzzle.id,
            exercise_slug="pin",
            mode="practice",
            result="correct",
            answer_json={},
        )
    )
    billing.ensure_default_plans(db_session)
    coupon = billing.create_coupon(
        db_session, code="P13PROFILE", discount_type="free_trial", trial_days=7
    )
    billing.redeem_coupon(db_session, user_id=user.id, code=coupon.code)
    db_session.commit()

    listed = client.get("/api/v1/admin/users?search=p13_profile_user", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json() if item["id"] == user.id)
    assert row["current_plan_code"] == "premium"
    assert row["current_plan_status"] in ("trialing", "active")
    assert row["phone_verified"] is True
    assert row["verification_channel"] == "telegram"
    assert row["attempts_count"] == 1
    assert row["coupon_redemption_count"] == 1
    assert row["last_active_at"] is not None
    assert "+989121234567" not in listed.text
    assert "secret123" not in listed.text

    profile = client.get(f"/api/v1/admin/users/{user.id}/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["overview"]["phone_verified"] is True
    assert body["overview"]["verification_channel"] == "telegram"
    assert body["overview"]["phone_masked"] == "+98912***4567"
    assert body["verification"]["channel"] == "telegram"
    assert "+989121234567" not in profile.text
    assert "token" not in profile.text.lower()


def test_health_exposes_only_safe_provider_and_channel_availability(client, db_session, monkeypatch):
    headers = _admin_headers(client, db_session)
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-secret-test")
    monkeypatch.setenv("BALE_BOT_TOKEN", "bale-secret-test")

    system = client.get("/api/v1/admin/system/health", headers=headers)
    assert system.status_code == 200, system.text
    assert "providers" in system.json()
    assert "channels" in system.json()
    assert system.json()["providers"]["telegram"]["configured"] is True
    assert system.json()["channels"]["telegram"]["available"] is True
    assert system.json()["providers"]["verification"]["telegram_available"] is False
    assert "telegram-secret-test" not in system.text
    assert "private-test" not in system.text

    provider = client.get("/api/v1/admin/system/provider-health", headers=headers)
    assert provider.status_code == 200, provider.text
    assert provider.json()["channels"]["web_push"]["subscriptions"] == 0
    assert provider.json()["billing"] == {"provider": "none", "available": False}
    assert "telegram-secret-test" not in provider.text
    assert "bale-secret-test" not in provider.text
