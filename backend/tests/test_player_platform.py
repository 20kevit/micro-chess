"""Phase 3 player platform: profile, identities, history, progress, dashboard."""

from sqlalchemy import inspect

from app.db.migration import SCHEMA_VERSION, ensure_schema


def _register(client, username="player_one", password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username="player_one"):
    return _register(client, username=username).json()["access_token"]


def _seeded_puzzle(db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.puzzles.models import Puzzle

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def _submit(client, token, puzzle_id, answer=None, mode="practice"):
    return client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle_id, "answer": answer or {}, "mode": mode},
        headers=_bearer(token),
    )


# --- auth boundaries --------------------------------------------------------


def test_player_endpoints_require_authentication(client):
    paths = [
        "/api/v1/me/profile",
        "/api/v1/me/chess-identities",
        "/api/v1/me/training/attempts",
        "/api/v1/me/training/attempts/1",
        "/api/v1/me/progress",
        "/api/v1/me/progress/piece-recognition",
        "/api/v1/me/dashboard",
    ]
    for path in paths:
        res = client.get(path)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "AUTH_REQUIRED"


def test_exercise_detail_is_public_but_unknown_slug_404s(client, db_session):
    _seeded_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    ok = client.get(f"/api/v1/exercises/{SLUG}")
    assert ok.status_code == 200
    assert ok.json()["slug"] == SLUG
    assert set(ok.json()) == {"slug", "title_fa", "title_en", "description", "is_active"}

    missing = client.get("/api/v1/exercises/no-such-exercise")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "EXERCISE_NOT_FOUND"


# --- profile -----------------------------------------------------------------


def test_profile_is_created_lazily_and_exposes_no_secrets(client):
    token = _token(client)
    res = client.get("/api/v1/me/profile", headers=_bearer(token))
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"display_name", "bio", "avatar_reference", "updated_at"}
    assert body["display_name"] == "player_one"
    assert body["bio"] == ""


def test_profile_update_and_validation(client):
    token = _token(client)
    headers = _bearer(token)
    ok = client.patch(
        "/api/v1/me/profile",
        json={"display_name": "  Omid  ", "bio": "شطرنج‌باز"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["display_name"] == "Omid"
    assert ok.json()["bio"] == "شطرنج‌باز"

    assert client.patch("/api/v1/me/profile", json={"display_name": "  "}, headers=headers).status_code == 422
    assert (
        client.patch("/api/v1/me/profile", json={"display_name": "x" * 101}, headers=headers).status_code
        == 422
    )
    assert (
        client.patch("/api/v1/me/profile", json={"bio": "x" * 501}, headers=headers).status_code == 422
    )
    assert (
        client.patch(
            "/api/v1/me/profile", json={"avatar_reference": "../secret"}, headers=headers
        ).status_code
        == 422
    )


def test_profile_update_ignores_privilege_escalation_payload(client, db_session):
    from app.modules.users.models import User

    token = _token(client)
    res = client.patch(
        "/api/v1/me/profile",
        json={"display_name": "Kid", "roles": ["ADMIN"], "is_active": False},
        headers=_bearer(token),
    )
    assert res.status_code == 200
    user = db_session.query(User).filter(User.username == "player_one").one()
    assert [r.role for r in user.roles] == ["PLAYER"]
    assert user.is_active is True


# --- external identities -------------------------------------------------------


def test_identity_lifecycle_and_verification_is_server_controlled(client):
    token = _token(client)
    headers = _bearer(token)
    added = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "lichess", "username": "Omid_77", "rating": 1500, "rating_type": "rapid",
                "is_verified": True},
        headers=headers,
    )
    assert added.status_code == 201, added.json()
    body = added.json()
    assert body["provider"] == "lichess"
    assert body["username"] == "omid_77"
    assert body["rating"] == 1500
    assert body["is_verified"] is False

    listed = client.get("/api/v1/me/chess-identities", headers=headers)
    assert [row["username"] for row in listed.json()] == ["omid_77"]

    patched = client.patch(
        f"/api/v1/me/chess-identities/{body['id']}",
        json={"rating": 1600, "is_verified": True},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["rating"] == 1600
    assert patched.json()["is_verified"] is False

    cleared = client.patch(
        f"/api/v1/me/chess-identities/{body['id']}", json={"rating": None}, headers=headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["rating"] is None

    assert client.delete(f"/api/v1/me/chess-identities/{body['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/me/chess-identities", headers=headers).json() == []


def test_identity_uniqueness_and_provider_allowlist(client):
    alice = _token(client, "alice")
    bob = _token(client, "bob")

    assert (
        client.post(
            "/api/v1/me/chess-identities",
            json={"provider": "fide", "username": "12345"},
            headers=_bearer(alice),
        ).status_code
        == 201
    )
    # Same provider account cannot link to a second MicroChess account.
    dup = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "fide", "username": "12345"},
        headers=_bearer(bob),
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "IDENTITY_TAKEN"
    # One identity per provider per player (case-insensitive).
    second = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "FIDE", "username": "other"},
        headers=_bearer(alice),
    )
    assert second.status_code == 409

    bad_provider = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "chess24", "username": "x"},
        headers=_bearer(alice),
    )
    assert bad_provider.status_code == 422
    bad_rating = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "lichess", "username": "zz", "rating": 99999},
        headers=_bearer(alice),
    )
    assert bad_rating.status_code == 422


def test_identity_cross_user_access_is_denied(client):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    identity_id = (
        client.post(
            "/api/v1/me/chess-identities",
            json={"provider": "lichess", "username": "alice_acc"},
            headers=_bearer(alice),
        )
        .json()["id"]
    )
    # Bob sees none of Alice's identities and cannot touch them (404, no leak).
    assert client.get("/api/v1/me/chess-identities", headers=_bearer(bob)).json() == []
    assert (
        client.patch(
            f"/api/v1/me/chess-identities/{identity_id}", json={"rating": 1}, headers=_bearer(bob)
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/me/chess-identities/{identity_id}", headers=_bearer(bob)).status_code
        == 404
    )
    assert client.get("/api/v1/me/chess-identities", headers=_bearer(alice)).json() != []


# --- training history ------------------------------------------------------------


def test_history_empty_ordering_filters_and_pagination(client, db_session):
    token = _token(client)
    headers = _bearer(token)
    assert client.get("/api/v1/me/training/attempts", headers=headers).json() == []

    puzzle = _seeded_puzzle(db_session)
    first = _submit(client, token, puzzle.id, {"selected_squares": []}).json()
    second = _submit(client, token, puzzle.id, {"selected_squares": []}).json()

    listed = client.get("/api/v1/me/training/attempts", headers=headers).json()
    assert [row["id"] for row in listed] == [second["id"], first["id"]]
    assert set(listed[0]) == {
        "id", "puzzle_id", "exercise_slug", "mode", "result",
        "score", "duration_ms", "hints_used", "created_at",
        "rating_before", "rating_delta", "rating_after",
        "xp_awarded",
    }

    by_exercise = client.get(
        f"/api/v1/me/training/attempts?exercise={puzzle.exercise_slug}", headers=headers
    ).json()
    assert len(by_exercise) == 2
    assert client.get("/api/v1/me/training/attempts?exercise=other", headers=headers).json() == []
    assert (
        len(client.get("/api/v1/me/training/attempts?mode=practice", headers=headers).json()) == 2
    )
    assert client.get("/api/v1/me/training/attempts?mode=rated", headers=headers).json() == []
    assert (
        client.get("/api/v1/me/training/attempts?page=1&page_size=1", headers=headers).json()[0]["id"]
        == second["id"]
    )
    too_big = client.get("/api/v1/me/training/attempts?page_size=1000", headers=headers)
    assert too_big.status_code == 422

    detail = client.get(f"/api/v1/me/training/attempts/{first['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["puzzle_id"] == puzzle.id
    assert client.get("/api/v1/me/training/attempts/999999", headers=headers).status_code == 404


def test_history_is_strictly_owned_and_guest_attempts_stay_private(client, db_session):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    puzzle = _seeded_puzzle(db_session)
    attempt_id = _submit(client, alice, puzzle.id, {"selected_squares": []}).json()["id"]

    assert client.get("/api/v1/me/training/attempts", headers=_bearer(bob)).json() == []
    foreign = client.get(f"/api/v1/me/training/attempts/{attempt_id}", headers=_bearer(bob))
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"

    # Guest practice is blocked server-side: no guest attempt is ever
    # created, so nothing can leak into any account's history.
    guest_token = client.post("/api/v1/guest/session").json()["guest_token"]
    guest_attempt = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "practice"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert guest_attempt.status_code == 401
    history = client.get("/api/v1/me/training/attempts", headers=_bearer(alice)).json()
    assert [row["id"] for row in history] == [attempt_id]


def _seed_historical_guest_attempt(db_session, guest_token, puzzle):
    """Persist one pre-decision guest attempt directly (history is kept)."""
    from app.modules.auth import service as auth_service
    from app.modules.progress.models import Attempt

    guest = auth_service.get_guest_session(db_session, guest_token)
    assert guest is not None
    attempt = Attempt(
        user_id=None,
        guest_session_id=guest.id,
        puzzle_id=puzzle.id,
        exercise_slug=puzzle.exercise_slug,
        mode="practice",
        result="correct",
        answer_json=dict(puzzle.answer_json or {}),
        score=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_migrated_guest_history_surfaces_in_player_history(client, db_session):
    token = _token(client)
    puzzle = _seeded_puzzle(db_session)
    guest_token = client.post("/api/v1/guest/session").json()["guest_token"]
    _seed_historical_guest_attempt(db_session, guest_token, puzzle)
    assert client.get("/api/v1/me/training/attempts", headers=_bearer(token)).json() == []
    migrated = client.post(
        "/api/v1/guest/migrate", json={"guest_token": guest_token}, headers=_bearer(token)
    )
    assert migrated.status_code == 200
    history = client.get("/api/v1/me/training/attempts", headers=_bearer(token)).json()
    assert len(history) == 1
    assert history[0]["puzzle_id"] == puzzle.id


# --- progress ----------------------------------------------------------------------


def test_progress_empty_and_aggregated(client, db_session):
    token = _token(client)
    headers = _bearer(token)
    empty = client.get("/api/v1/me/progress", headers=headers).json()
    assert empty == {"attempts": 0, "correct": 0, "accuracy": 0.0, "exercises": []}

    puzzle = _seeded_puzzle(db_session)
    correct_answer = {"selected_squares": list(puzzle.answer_json.get("squares", []))}
    correct_res = _submit(client, token, puzzle.id, correct_answer)
    assert correct_res.json()["result"] == "correct"
    _submit(client, token, puzzle.id, {"selected_squares": ["a1"]})

    progress = client.get("/api/v1/me/progress", headers=headers).json()
    assert progress["attempts"] == 2
    assert progress["correct"] == 1
    assert progress["accuracy"] == 0.5
    assert len(progress["exercises"]) == 1
    entry = progress["exercises"][0]
    assert entry["exercise"] == puzzle.exercise_slug
    assert entry["attempts"] == 2
    assert entry["correct"] == 1
    assert entry["accuracy"] == 0.5
    assert entry["last_practiced_at"]

    only_correct = client.get("/api/v1/me/training/attempts?correct=true", headers=headers).json()
    assert len(only_correct) == 1
    assert only_correct[0]["result"] == "correct"
    only_wrong = client.get("/api/v1/me/training/attempts?correct=false", headers=headers).json()
    assert len(only_wrong) == 1
    assert only_wrong[0]["result"] != "correct"

    per_exercise = client.get(
        f"/api/v1/me/progress/{puzzle.exercise_slug}", headers=headers
    ).json()
    assert per_exercise["attempts"] == 2
    assert client.get("/api/v1/me/progress/no-such-exercise", headers=headers).status_code == 404


def test_progress_is_strictly_owned(client, db_session):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    puzzle = _seeded_puzzle(db_session)
    _submit(client, alice, puzzle.id, dict(puzzle.answer_json))

    alice_progress = client.get("/api/v1/me/progress", headers=_bearer(alice)).json()
    bob_progress = client.get("/api/v1/me/progress", headers=_bearer(bob)).json()
    assert alice_progress["attempts"] == 1
    assert bob_progress == {"attempts": 0, "correct": 0, "accuracy": 0.0, "exercises": []}


# --- dashboard -----------------------------------------------------------------------


def test_dashboard_read_model_for_new_and_active_players(client, db_session):
    token = _token(client)
    headers = _bearer(token)
    fresh = client.get("/api/v1/me/dashboard", headers=headers).json()
    assert set(fresh) == {"profile", "progress", "recent_attempts"}
    assert fresh["progress"]["attempts"] == 0
    assert fresh["recent_attempts"] == []
    assert fresh["profile"]["display_name"] == "player_one"

    puzzle = _seeded_puzzle(db_session)
    for _ in range(7):
        _submit(client, token, puzzle.id, {"selected_squares": []})
    active = client.get("/api/v1/me/dashboard", headers=headers).json()
    assert active["progress"]["attempts"] == 7
    assert len(active["recent_attempts"]) == 5
    ids = [row["id"] for row in active["recent_attempts"]]
    assert ids == sorted(ids, reverse=True)


# --- migration -------------------------------------------------------------------------


def test_schema_v6_creates_gamification_and_audit_tables_and_upgrades_cleanly():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    assert ensure_schema(engine) == SCHEMA_VERSION
    tables = inspect(engine).get_table_names()
    assert "player_profiles" in tables
    assert "player_external_identities" in tables
    assert "player_ratings" in tables
    assert "rating_events" in tables
    assert "player_gamification_state" in tables
    assert "xp_events" in tables
    assert "player_streaks" in tables
    assert "player_achievements" in tables
    assert "audit_logs" in tables
    attempt_cols = {c["name"] for c in inspect(engine).get_columns("attempts")}
    assert {"rating_before", "rating_delta", "rating_after", "xp_awarded"} <= attempt_cols
    # Idempotent re-run.
    assert ensure_schema(engine) == SCHEMA_VERSION
