"""Phase 8 analytics: derived read-only metrics over authoritative history.

Covers empty/populated contracts, denominators, practice vs rated,
UTC date-range boundaries, exercise filtering, period comparison,
rating/XP trend reconciliation, observed difficulty, admin aggregates,
isolation, authorization, pagination, and source-data immutability.
"""

from datetime import datetime, timedelta, timezone

from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.models import RatingEvent
from app.modules.gamification_engine.models import XpEvent
from app.modules.users.models import User, UserRole


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _make_admin(db_session, username):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, "ADMIN")) is None:
        db_session.add(UserRole(user_id=user.id, role="ADMIN"))
        db_session.commit()
    return user


def _admin_token(client, db_session, username="analytics_admin"):
    token = _register(client, username).json()["access_token"]
    _make_admin(db_session, username)
    return token


def _seeded_piece_puzzle(db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    assert len(puzzle.answer_json.get("squares", [])) >= 2
    return puzzle


def _submit(client, token, puzzle_id, answer, mode="practice"):
    return client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle_id, "answer": answer, "mode": mode},
        headers=_bearer(token),
    )


def _correct(puzzle):
    return {"selected_squares": list(puzzle.answer_json["squares"])}


def _wrong():
    return {"selected_squares": ["not-a-square"]}


def _partial(puzzle):
    squares = list(puzzle.answer_json["squares"])
    return {"selected_squares": [squares[0], "not-a-square"]}


def _backdate_attempt(db_session, attempt_id, days_ago):
    """Move an attempt and its derived events back in time (UTC, naive)."""
    moment = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    attempt = db_session.get(Attempt, attempt_id)
    attempt.created_at = moment
    event = db_session.query(RatingEvent).filter(RatingEvent.attempt_id == attempt_id).first()
    if event is not None:
        event.created_at = moment
    xp = db_session.query(XpEvent).filter(XpEvent.attempt_id == attempt_id).first()
    if xp is not None:
        xp.created_at = moment
    db_session.commit()


def _counts(db_session):
    return {
        "attempts": db_session.query(Attempt).count(),
        "rating_events": db_session.query(RatingEvent).count(),
        "xp_events": db_session.query(XpEvent).count(),
        "puzzles": db_session.query(Puzzle).count(),
    }


# --- authorization ------------------------------------------------------------


def test_player_analytics_require_authentication(client):
    for path in [
        "/api/v1/me/analytics",
        "/api/v1/me/analytics/comparison",
        "/api/v1/me/analytics/exercises/piece-recognition",
        "/api/v1/me/analytics/puzzles/1",
    ]:
        res = client.get(path)
        assert res.status_code == 401, path


def test_admin_analytics_require_admin(client, db_session):
    token = _token(client, "regular_player")
    for path in [
        "/api/v1/admin/analytics",
        "/api/v1/admin/analytics/exercises",
        "/api/v1/admin/analytics/exercises/piece-recognition",
        "/api/v1/admin/analytics/puzzles",
        "/api/v1/admin/analytics/puzzles/1",
    ]:
        res = client.get(path, headers=_bearer(token))
        assert res.status_code == 403, path
    # Anonymous is rejected before authorization.
    assert client.get("/api/v1/admin/analytics").status_code == 401


# --- empty contracts ------------------------------------------------------------


def test_empty_player_analytics_is_valid(client):
    token = _token(client, "fresh_player")
    res = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token))
    assert res.status_code == 200
    body = res.json()
    assert body["totals"]["attempts"] == 0
    assert body["totals"]["accuracy"] == 0.0
    assert body["totals"]["avg_response_ms"] is None
    assert body["totals"]["active_days"] == 0
    assert body["by_mode"] == []
    assert body["by_exercise"] == []
    assert body["daily"] == []
    assert body["ratings"] == []
    assert body["xp"]["total"] == 0
    assert body["streak"] == {"current": 0, "longest": 0}


def test_empty_admin_analytics_is_valid(client, db_session):
    token = _admin_token(client, db_session)
    res = client.get("/api/v1/admin/analytics?period=all", headers=_bearer(token))
    assert res.status_code == 200
    body = res.json()
    assert body["users_total"] >= 1
    assert body["active_users"] == 0
    assert body["totals"]["attempts"] == 0
    assert body["totals"]["accuracy"] == 0.0
    assert body["comparison"] is None  # all-time has no previous period


# --- populated totals + denominators ----------------------------------------------


def test_populated_totals_reconcile(client, db_session):
    token = _token(client, "trainee_one")
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200
    assert _submit(client, token, puzzle.id, _partial(puzzle)).status_code == 200
    assert _submit(client, token, puzzle.id, _wrong()).status_code == 200

    body = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token)).json()
    totals = body["totals"]
    assert totals["attempts"] == 3
    assert totals["correct"] == 1
    assert totals["partial"] == 1
    assert totals["wrong"] == 1
    # Accuracy denominator is ALL attempts (matches progress_summary).
    assert totals["accuracy"] == 1 / 3
    assert totals["correct"] + totals["partial"] + totals["wrong"] + totals["terminal"] == totals["attempts"]
    assert totals["active_days"] == 1
    assert totals["total_practice_ms"] >= 0
    modes = {entry["mode"]: entry for entry in body["by_mode"]}
    assert modes["practice"]["attempts"] == 3
    assert modes["practice"]["accuracy"] == 1 / 3
    assert len(body["by_exercise"]) == 1
    assert body["by_exercise"][0]["attempts"] == 3
    assert body["daily"] and sum(b["attempts"] for b in body["daily"]) == 3


def test_practice_attempts_do_not_rate_but_earn_xp(client, db_session):
    token = _token(client, "practice_only")
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle), mode="practice").status_code == 200

    body = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token)).json()
    assert body["ratings"] == []
    assert body["xp"]["earned_in_period"] == 10
    assert body["xp"]["events_in_period"] == 1
    assert body["xp"]["total"] == 10


def test_rated_attempts_reconcile_with_rating_history(client, db_session):
    from app.modules.piece_recognition.validator import SLUG

    token = _token(client, "rated_player")
    puzzle = _seeded_piece_puzzle(db_session)
    first = _submit(client, token, puzzle.id, _correct(puzzle), mode="rated")
    second = _submit(client, token, puzzle.id, _wrong(), mode="rated")
    assert first.status_code == 200 and second.status_code == 200

    body = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token)).json()
    trends = {item["exercise"]: item for item in body["ratings"]}
    assert SLUG in trends
    trend = trends[SLUG]
    assert trend["events_in_period"] == 2
    assert trend["current"] is not None
    assert trend["games"] == 2

    history = client.get(f"/api/v1/me/ratings/{SLUG}/history", headers=_bearer(token)).json()
    expected_delta = round(sum(item["delta"] for item in history["items"]), 2)
    assert trend["delta_in_period"] == expected_delta

    detail = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert trend["current"] == detail["rating"]

    modes = {entry["mode"]: entry for entry in body["by_mode"]}
    assert modes["rated"]["attempts"] == 2


# --- date ranges + UTC boundaries ---------------------------------------------------


def test_rolling_window_excludes_old_attempts(client, db_session):
    token = _token(client, "time_traveller")
    puzzle = _seeded_piece_puzzle(db_session)
    old_id = _submit(client, token, puzzle.id, _correct(puzzle)).json()["id"]
    new_id = _submit(client, token, puzzle.id, _wrong()).json()["id"]
    _backdate_attempt(db_session, old_id, days_ago=10)
    _ = new_id

    week = client.get("/api/v1/me/analytics?period=7d", headers=_bearer(token)).json()
    assert week["totals"]["attempts"] == 1
    assert week["totals"]["wrong"] == 1
    everything = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token)).json()
    assert everything["totals"]["attempts"] == 2


def test_custom_range_is_inclusive_per_utc_day(client, db_session):
    token = _token(client, "custom_ranger")
    puzzle = _seeded_piece_puzzle(db_session)
    attempt_id = _submit(client, token, puzzle.id, _correct(puzzle)).json()["id"]
    _backdate_attempt(db_session, attempt_id, days_ago=5)
    day = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()

    inside = client.get(
        f"/api/v1/me/analytics?period=custom&date_from={day}&date_to={day}",
        headers=_bearer(token),
    )
    assert inside.status_code == 200
    assert inside.json()["totals"]["attempts"] == 1

    other_day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    outside = client.get(
        f"/api/v1/me/analytics?period=custom&date_from={other_day}&date_to={other_day}",
        headers=_bearer(token),
    )
    assert outside.json()["totals"]["attempts"] == 0


def test_invalid_periods_rejected(client):
    token = _token(client, "picky_player")
    assert client.get("/api/v1/me/analytics?period=forever", headers=_bearer(token)).status_code == 422
    assert client.get("/api/v1/me/analytics?period=custom", headers=_bearer(token)).status_code == 422
    res = client.get(
        "/api/v1/me/analytics?period=custom&date_from=2026-02-01&date_to=2026-01-01",
        headers=_bearer(token),
    )
    assert res.status_code == 422


# --- exercise filtering --------------------------------------------------------------


def test_exercise_filter_and_detail(client, db_session):
    from app.modules.piece_recognition.validator import SLUG

    token = _token(client, "filtered_player")
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200

    filtered = client.get(
        f"/api/v1/me/analytics?period=all&exercise={SLUG}", headers=_bearer(token)
    ).json()
    assert filtered["totals"]["attempts"] == 1
    assert filtered["exercise"] == SLUG

    unknown = client.get("/api/v1/me/analytics?period=all&exercise=nope", headers=_bearer(token))
    assert unknown.status_code == 404

    detail = client.get(
        f"/api/v1/me/analytics/exercises/{SLUG}?period=all", headers=_bearer(token)
    ).json()
    assert detail["totals"]["attempts"] == 1
    assert client.get(
        "/api/v1/me/analytics/exercises/nope?period=all", headers=_bearer(token)
    ).status_code == 404


# --- comparison --------------------------------------------------------------


def test_period_comparison_current_vs_previous(client, db_session):
    token = _token(client, "comparing_player")
    puzzle = _seeded_piece_puzzle(db_session)
    old_id = _submit(client, token, puzzle.id, _correct(puzzle)).json()["id"]
    assert _submit(client, token, puzzle.id, _wrong()).status_code == 200
    assert _submit(client, token, puzzle.id, _wrong()).status_code == 200
    # Previous 30d window is days 30-60: backdate well inside it.
    _backdate_attempt(db_session, old_id, days_ago=40)

    body = client.get("/api/v1/me/analytics/comparison?period=30d", headers=_bearer(token)).json()
    assert body["current"]["attempts"] == 2
    assert body["previous"]["attempts"] == 1
    assert body["delta"]["attempts"] == 1
    # Previous window had the only correct attempt: accuracy dropped.
    assert body["previous"]["accuracy"] == 1.0
    assert body["current"]["accuracy"] == 0.0
    assert body["delta"]["accuracy"] == -1.0


def test_comparison_rejects_all_time(client):
    token = _token(client, "comparison_player")
    res = client.get("/api/v1/me/analytics/comparison?period=all", headers=_bearer(token))
    assert res.status_code == 422


# --- personal puzzle analytics ---------------------------------------------------


def test_personal_puzzle_analytics_never_exposes_answers(client, db_session):
    token = _token(client, "puzzle_person")
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200
    assert _submit(client, token, puzzle.id, _wrong()).status_code == 200

    res = client.get(f"/api/v1/me/analytics/puzzles/{puzzle.id}", headers=_bearer(token))
    assert res.status_code == 200
    body = res.json()
    assert body["attempts"] == 2
    assert body["correct"] == 1
    assert body["accuracy"] == 0.5
    assert "answer_json" not in body
    assert "answer" not in " ".join(body.keys())
    assert client.get("/api/v1/me/analytics/puzzles/999999", headers=_bearer(token)).status_code == 404


# --- isolation ------------------------------------------------------------------


def test_player_analytics_are_isolated(client, db_session):
    token_a = _token(client, "isolated_a")
    token_b = _token(client, "isolated_b")
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token_a, puzzle.id, _correct(puzzle)).status_code == 200

    body_b = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token_b)).json()
    assert body_b["totals"]["attempts"] == 0
    body_a = client.get("/api/v1/me/analytics?period=all", headers=_bearer(token_a)).json()
    assert body_a["totals"]["attempts"] == 1


# --- admin aggregates --------------------------------------------------------------


def test_admin_platform_matches_seeded_state(client, db_session):
    token = _token(client, "seeded_player")
    admin = _admin_token(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle), mode="rated").status_code == 200
    assert _submit(client, token, puzzle.id, _wrong(), mode="practice").status_code == 200

    body = client.get("/api/v1/admin/analytics?period=all", headers=_bearer(admin)).json()
    assert body["totals"]["attempts"] == 2
    assert body["totals"]["correct"] == 1
    assert body["active_users"] == 1
    assert body["users_total"] == 2
    assert body["ratings"]["events_in_period"] == 1
    assert body["xp"]["events_in_period"] == 2
    assert body["xp"]["earned_in_period"] == 12  # correct 10 + wrong 2
    usage = {entry["exercise"]: entry for entry in body["exercise_usage"]}
    assert sum(entry["attempts"] for entry in usage.values()) == 2
    payload = res_json_text(client, "/api/v1/admin/analytics?period=all", admin)
    assert "password_hash" not in payload
    assert "access_token" not in payload
    assert "answer_json" not in payload


def res_json_text(client, path, token):
    res = client.get(path, headers=_bearer(token))
    assert res.status_code == 200
    return res.text


def test_admin_exercise_analytics(client, db_session):
    from app.modules.piece_recognition.validator import SLUG

    token = _token(client, "exercise_fan")
    admin = _admin_token(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle), mode="rated").status_code == 200

    items = client.get("/api/v1/admin/analytics/exercises?period=all", headers=_bearer(admin)).json()
    row = next(item for item in items if item["exercise"] == SLUG)
    assert row["attempts"] == 1
    assert row["unique_players"] == 1
    assert row["accuracy"] == 1.0
    assert row["rating_events_in_period"] == 1
    assert row["current_ratings"] == 1
    assert row["puzzles_published"] >= 1

    detail = client.get(
        f"/api/v1/admin/analytics/exercises/{SLUG}?period=all", headers=_bearer(admin)
    ).json()
    assert detail["attempts"] == 1
    assert detail["unique_players"] == 1
    assert sum(b["attempts"] for b in detail["daily"]) == 1
    assert client.get(
        "/api/v1/admin/analytics/exercises/nope?period=all", headers=_bearer(admin)
    ).status_code == 404


def test_admin_puzzle_analytics_and_observed_difficulty(client, db_session):
    token_a = _token(client, "observer_a")
    token_b = _token(client, "observer_b")
    admin = _admin_token(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)

    # Easy puzzle: 5 correct from two players.
    for _ in range(3):
        assert _submit(client, token_a, puzzle.id, _correct(puzzle)).status_code == 200
    for _ in range(2):
        assert _submit(client, token_b, puzzle.id, _correct(puzzle)).status_code == 200

    items = client.get("/api/v1/admin/analytics/puzzles?period=all", headers=_bearer(admin)).json()
    row = next(item for item in items if item["puzzle_id"] == puzzle.id)
    assert row["attempts"] == 5
    assert row["unique_players"] == 2
    assert row["accuracy"] == 1.0
    assert row["observed_difficulty"] == "easy"
    assert row["failure_rate"] == 0.0
    assert row["repeated_failures"] == 0
    assert "answer_json" not in row

    detail = client.get(
        f"/api/v1/admin/analytics/puzzles/{puzzle.id}?period=all", headers=_bearer(admin)
    ).json()
    assert detail["observed_difficulty"] == "easy"
    assert "answer_json" not in detail
    assert client.get("/api/v1/admin/analytics/puzzles/999999?period=all", headers=_bearer(admin)).status_code == 404


def test_observed_difficulty_hard_and_insufficient(client, db_session):
    token = _token(client, "struggler")
    admin = _admin_token(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    for _ in range(5):
        assert _submit(client, token, puzzle.id, _wrong()).status_code == 200

    row = next(
        item
        for item in client.get("/api/v1/admin/analytics/puzzles?period=all", headers=_bearer(admin)).json()
        if item["puzzle_id"] == puzzle.id
    )
    assert row["observed_difficulty"] == "hard"
    # One user failed the same puzzle 5 times: repeated failure.
    assert row["repeated_failures"] == 1

    # Fresh puzzle with a single attempt: not enough data.
    from app.modules.piece_recognition import seed as seed_mod

    seed_mod.seed_db(db_session)
    other = (
        db_session.query(Puzzle)
        .filter(Puzzle.id != puzzle.id)
        .order_by(Puzzle.id)
        .first()
    )
    assert _submit(client, token, other.id, _correct(other)).status_code == 200
    rows = {
        item["puzzle_id"]: item
        for item in client.get("/api/v1/admin/analytics/puzzles?period=all", headers=_bearer(admin)).json()
    }
    assert rows[other.id]["observed_difficulty"] == "insufficient_data"


def test_admin_puzzle_pagination(client, db_session):
    admin = _admin_token(client, db_session)
    _seeded_piece_puzzle(db_session)
    first = client.get("/api/v1/admin/analytics/puzzles?page=1&page_size=1", headers=_bearer(admin))
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert client.get("/api/v1/admin/analytics/puzzles?page_size=500", headers=_bearer(admin)).status_code == 422


# --- immutability --------------------------------------------------------------------


def test_analytics_requests_do_not_mutate_source_data(client, db_session):
    token = _token(client, "immutable_player")
    admin = _admin_token(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    assert _submit(client, token, puzzle.id, _correct(puzzle), mode="rated").status_code == 200

    before = _counts(db_session)
    for path, tok in [
        ("/api/v1/me/analytics?period=all", token),
        ("/api/v1/me/analytics/comparison?period=7d", token),
        (f"/api/v1/me/analytics/puzzles/{puzzle.id}", token),
        ("/api/v1/admin/analytics?period=all", admin),
        ("/api/v1/admin/analytics/exercises?period=all", admin),
        ("/api/v1/admin/analytics/puzzles?period=all", admin),
        (f"/api/v1/admin/analytics/puzzles/{puzzle.id}?period=all", admin),
    ]:
        res = client.get(path, headers=_bearer(tok))
        assert res.status_code == 200, path
    assert _counts(db_session) == before
