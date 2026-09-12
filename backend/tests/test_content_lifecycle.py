"""Phase 07 content & generators: lifecycle, validation, review/approval,
generators, unpublished isolation, authorization, and audit."""

import random

from app.modules.admin.models import AuditLog
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle
from app.modules.users.models import User, UserRole


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _make_admin(db_session, username):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, "ADMIN")) is None:
        db_session.add(UserRole(user_id=user.id, role="ADMIN"))
        db_session.commit()
    return user


def _admin_token(client, db_session, username="the_admin"):
    _register(client, username=username)
    _make_admin(db_session, username)
    # The pre-promotion session stays PLAYER-active (sessions fix their
    # role at creation); open a fresh ADMIN-active session instead.
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123", "role": "ADMIN"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _seed_exercise(db_session, slug="pin"):
    exercise = db_session.get(Exercise, slug)
    if exercise is None:
        exercise = Exercise(
            slug=slug, title_fa="آچمز", title_en="Pin",
            description="desc", is_active=True, sort_order=1,
        )
        db_session.add(exercise)
        db_session.commit()
    return exercise


def _draft(client, headers, slug="pin", **fields):
    body = {"exercise_slug": slug, "answer_json": {"moves": ["e2e4"]}, "prompt_fa": "سوال"}
    body.update(fields)
    res = client.post("/api/v1/admin/puzzles", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _walk_to_published(client, headers, pid):
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers).status_code == 200
    assert client.post(
        f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers
    ).status_code == 200
    assert client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers).status_code == 200
    pub = client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return pub.json()


# --- validation ---------------------------------------------------------------


def test_validate_rejects_missing_answer(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers, answer_json={})["id"]
    res = client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "draft"
    history = client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=headers).json()
    assert history["validations"][0]["status"] == "fail"
    assert any(e["code"] == "answer_missing" for e in history["validations"][0]["result"]["errors"])


def test_validate_rejects_invalid_fen(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers, fen="not-a-fen")["id"]
    client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    history = client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=headers).json()
    assert history["validations"][0]["status"] == "fail"
    assert any(e["code"] == "invalid_fen" for e in history["validations"][0]["result"]["errors"])


def test_validate_rejects_answer_leakage(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    leaked = {"moves": ["e2e4"]}
    pid = _draft(client, headers, answer_json=leaked, position_json=dict(leaked))["id"]
    client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    history = client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=headers).json()
    assert any(e["code"] == "answer_leakage" for e in history["validations"][0]["result"]["errors"])


def test_validate_rejects_duplicate_content(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    first = _draft(client, headers)["id"]
    second = _draft(client, headers)["id"]
    assert client.post(f"/api/v1/admin/puzzles/{first}/validate", headers=headers).json()["status"] == "validated"
    client.post(f"/api/v1/admin/puzzles/{second}/validate", headers=headers)
    history = client.get(f"/api/v1/admin/puzzles/{second}/history", headers=headers).json()
    assert history["validations"][0]["status"] == "fail"
    dup = [e for e in history["validations"][0]["result"]["errors"] if e["code"] == "duplicate_content"]
    assert dup and dup[0]["duplicate_of"] == first


def test_validate_checks_exercise_solution_legality(client, db_session):
    """Captures answers must match the recomputed legal capture set."""
    import app.modules.captures.content  # noqa: F401  (registers the hook)
    from app.modules.captures import generator as captures_gen

    admin = _admin_token(client, db_session)
    headers = _bearer(admin)
    data = captures_gen.generate_question_data(random.Random(11))
    good = _draft(
        client, headers, slug="captures",
        fen=data["fen"],
        position_json={"from": data["from"], "profile": data["profile"]},
        answer_json={"squares": data["squares"], "from": data["from"], "profile": data["profile"]},
    )["id"]
    assert client.post(f"/api/v1/admin/puzzles/{good}/validate", headers=headers).json()["status"] == "validated"

    bad = _draft(
        client, headers, slug="captures",
        fen=data["fen"],
        position_json={"from": data["from"], "profile": data["profile"]},
        answer_json={"squares": ["a1"], "from": data["from"], "profile": data["profile"]},
    )["id"]
    client.post(f"/api/v1/admin/puzzles/{bad}/validate", headers=headers)
    history = client.get(f"/api/v1/admin/puzzles/{bad}/history", headers=headers).json()
    codes = {e["code"] for e in history["validations"][0]["result"]["errors"]}
    assert "solution_mismatch" in codes


def test_create_rejects_bad_metadata(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    assert client.post("/api/v1/admin/puzzles", json={"exercise_slug": "pin", "difficulty": 9}, headers=headers).status_code == 422
    assert client.post("/api/v1/admin/puzzles", json={"exercise_slug": "pin", "source": "generated"}, headers=headers).status_code == 422
    assert client.post("/api/v1/admin/puzzles", json={"exercise_slug": "pin", "target_rating": 9999}, headers=headers).status_code == 422


# --- lifecycle transitions -----------------------------------------------------


def test_invalid_transitions_are_rejected(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    # Out-of-order gates.
    assert client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "bogus"}, headers=headers).status_code == 422
    # Full walk, then terminal states refuse further validation.
    _walk_to_published(client, headers, pid)
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers).status_code == 409
    client.post(f"/api/v1/admin/puzzles/{pid}/retire", headers=headers)
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers).status_code == 409
    assert client.get("/api/v1/admin/puzzles/999999/history", headers=headers).status_code == 404


def test_request_changes_returns_to_draft_for_correction(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers).json()["status"] == "validated"
    sent_back = client.post(
        f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "request_changes", "notes": "بازنویسی شود"}, headers=headers
    )
    assert sent_back.status_code == 200
    assert sent_back.json()["status"] == "draft"
    # Meaning is editable again in draft, then re-validates cleanly.
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"answer_json": {"moves": ["d2d4"]}}, headers=headers).status_code == 200
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers).json()["status"] == "validated"
    history = client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=headers).json()
    assert history["reviews"][0]["decision"] == "request_changes"
    assert history["reviews"][0]["notes"] == "بازنویسی شود"


def test_retired_content_is_fully_immutable(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    _walk_to_published(client, headers, pid)
    client.post(f"/api/v1/admin/puzzles/{pid}/retire", headers=headers)
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"prompt_fa": "تازه"}, headers=headers).status_code == 409
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"answer_json": {"moves": ["x"]}}, headers=headers).status_code == 409


def test_status_filters_cover_lifecycle(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    assert any(p["id"] == pid for p in client.get("/api/v1/admin/puzzles?status=draft", headers=headers).json())
    client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    assert any(p["id"] == pid for p in client.get("/api/v1/admin/puzzles?status=validated", headers=headers).json())
    assert client.get("/api/v1/admin/puzzles?status=bogus", headers=headers).status_code == 422


# --- unpublished isolation ------------------------------------------------------


def test_unpublished_content_hidden_from_players(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    player = _register(client, username="learner").json()["access_token"]
    player_headers = _bearer(player)

    for stage in ("draft", "validated", "reviewed", "approved"):
        pid = _draft(client, headers)["id"]
        if stage in ("validated", "reviewed", "approved"):
            client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
        if stage in ("reviewed", "approved"):
            client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers)
        if stage == "approved":
            client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers)
        assert client.get(f"/api/v1/puzzles/{pid}", headers=player_headers).status_code == 404
        attempt = client.post("/api/v1/attempts", json={
            "puzzle_id": pid, "answer": {"moves": ["e2e4"]}, "mode": "practice",
        }, headers=player_headers)
        assert attempt.status_code == 404

    # Listing never leaks drafts either.
    pid = _draft(client, headers)["id"]
    listing = client.get("/api/v1/puzzles", headers=player_headers).json()
    assert all(p["id"] != pid for p in listing)


def test_published_content_available_then_retired_preserves_history(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    player = _register(client, username="learner").json()["access_token"]
    player_headers = _bearer(player)
    pid = _draft(client, headers)["id"]
    _walk_to_published(client, headers, pid)
    assert client.get(f"/api/v1/puzzles/{pid}", headers=player_headers).status_code == 200
    ok = client.post("/api/v1/attempts", json={
        "puzzle_id": pid, "answer": {"moves": ["e2e4"]}, "mode": "practice",
    }, headers=player_headers)
    assert ok.status_code == 200
    client.post(f"/api/v1/admin/puzzles/{pid}/retire", headers=headers)
    assert client.get(f"/api/v1/puzzles/{pid}", headers=player_headers).status_code == 404
    history = client.get("/api/v1/me/training/attempts", headers=player_headers).json()
    assert len(history) == 1 and history[0]["puzzle_id"] == pid


# --- authorization ----------------------------------------------------------------


def test_content_endpoints_require_privileged_capabilities(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    player = _register(client, username="plain").json()["access_token"]
    player_headers = _bearer(player)

    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=player_headers).status_code == 403
    assert client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=player_headers).status_code == 403
    assert client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=player_headers).status_code == 403
    assert client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=player_headers).status_code == 403
    assert client.get("/api/v1/admin/generators", headers=player_headers).status_code == 403
    assert client.post("/api/v1/admin/generators/piece-recognition-v1/runs", json={"count": 1}, headers=player_headers).status_code == 403
    assert client.get("/api/v1/admin/generator-runs", headers=player_headers).status_code == 403
    # Anonymous callers get 401, not information.
    assert client.post(f"/api/v1/admin/puzzles/{pid}/validate").status_code == 401
    assert client.get("/api/v1/admin/generators").status_code == 401
    # State unchanged by denied requests.
    assert db_session.get(Puzzle, pid).status == "draft"


# --- generators ---------------------------------------------------------------------


def test_generator_registry_lists_versioned_generators(client, db_session):
    admin = _admin_token(client, db_session)
    res = client.get("/api/v1/admin/generators", headers=_bearer(admin))
    assert res.status_code == 200
    codes = {g["code"]: g for g in res.json()}
    assert set(codes) == {"piece-recognition-v1", "captures-v1", "legal-destinations-v1"}
    for generator in codes.values():
        assert generator["version"]
        assert generator["exercise_slug"]
        assert generator["status"] == "active"


def test_generator_run_produces_validated_candidates_with_provenance(client, db_session):
    admin = _admin_token(client, db_session)
    headers = _bearer(admin)
    res = client.post(
        "/api/v1/admin/generators/piece-recognition-v1/runs",
        json={"count": 2, "seed": 42, "target_rating": 950, "difficulty": 2},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    run = res.json()
    assert run["status"] == "completed"
    assert run["accepted_count"] == 2 and run["rejected_count"] == 0
    assert run["seed"] == 42 and run["generator_version"] == "1.0.0"
    assert run["target_rating"] == 950 and run["difficulty"] == 2
    assert len(run["result"]["accepted_puzzle_ids"]) == 2

    player = _register(client, username="learner").json()["access_token"]
    for pid in run["result"]["accepted_puzzle_ids"]:
        detail = client.get(f"/api/v1/admin/puzzles/{pid}", headers=headers).json()
        assert detail["status"] == "validated"
        assert detail["source"] == "generated"
        assert detail["generator_run_id"] == run["id"]
        assert detail["difficulty"] == 2
        # Generated content is never automatically production content.
        assert client.get(f"/api/v1/puzzles/{pid}", headers=_bearer(player)).status_code == 404

    # Generated candidates follow the normal review/approval gates.
    first = run["result"]["accepted_puzzle_ids"][0]
    _walk_to_published(client, headers, first)
    assert client.get(f"/api/v1/puzzles/{first}", headers=_bearer(player)).status_code == 200


def test_generator_dedup_and_determinism(client, db_session):
    from app.modules.generators.registry import get_generator

    # Pure candidate sequence is reproducible from the seed.
    definition = get_generator("captures-v1")
    left = definition.build_candidate(random.Random(7), {})
    right = definition.build_candidate(random.Random(7), {})
    assert left == right

    admin = _admin_token(client, db_session)
    headers = _bearer(admin)
    first = client.post(
        "/api/v1/admin/generators/captures-v1/runs", json={"count": 2, "seed": 7}, headers=headers
    ).json()
    assert first["status"] == "completed"
    assert first["accepted_count"] == 2
    # Replaying the same seed regenerates identical candidates, which
    # dedup rejects instead of duplicating production content.
    second = client.post(
        "/api/v1/admin/generators/captures-v1/runs", json={"count": 2, "seed": 7}, headers=headers
    ).json()
    assert second["status"] == "completed"
    assert second["accepted_count"] == 0
    assert second["rejected_count"] == 2
    assert all(r["reason"] == "validation_failed" for r in second["result"]["rejected"])


def test_generator_input_validation_and_cancel_safety(client, db_session):
    admin = _admin_token(client, db_session)
    headers = _bearer(admin)
    base = "/api/v1/admin/generators/piece-recognition-v1/runs"
    assert client.post("/api/v1/admin/generators/nope/runs", json={"count": 1}, headers=headers).status_code == 422
    assert client.post(base, json={"count": 0}, headers=headers).status_code == 422
    assert client.post(base, json={"count": 51}, headers=headers).status_code == 422
    assert client.post(base, json={"count": 1, "config": {"bogus": 1}}, headers=headers).status_code == 422
    assert client.post(base, json={"count": 1, "target_rating": 50}, headers=headers).status_code == 422
    assert client.post(base, json={"count": 1, "difficulty": 9}, headers=headers).status_code == 422

    run = client.post(base, json={"count": 1, "seed": 5}, headers=headers).json()
    assert run["status"] == "completed"
    # Terminal jobs cannot be cancelled; unknown jobs are 404.
    assert client.post(f"/api/v1/admin/generator-runs/{run['id']}/cancel", headers=headers).status_code == 409
    assert client.post("/api/v1/admin/generator-runs/999999/cancel", headers=headers).status_code == 404
    assert client.get("/api/v1/admin/generator-runs/999999", headers=headers).status_code == 404
    # History is filterable and configuration/version are preserved.
    listed = client.get("/api/v1/admin/generator-runs?generator=piece-recognition-v1", headers=headers).json()
    assert any(r["id"] == run["id"] and r["seed"] == 5 for r in listed)
    detail = client.get(f"/api/v1/admin/generator-runs/{run['id']}", headers=headers).json()
    assert detail["generator_version"] == "1.0.0"
    assert detail["requested_by_user_id"] is not None


# --- audit ------------------------------------------------------------------------------


def test_content_transitions_are_audited_without_secrets(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    pid = _draft(client, headers)["id"]
    client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers)
    client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers)
    client.post(
        "/api/v1/admin/generators/piece-recognition-v1/runs", json={"count": 1, "seed": 9}, headers=headers
    )
    actions = {row.action for row in db_session.query(AuditLog).all()}
    assert {"puzzles.validate", "puzzles.review", "puzzles.approve", "generators.run"} <= actions
    for row in db_session.query(AuditLog).all():
        assert row.actor_user_id is not None
        flat = str(row.metadata_json).lower()
        assert "password" not in flat and "token" not in flat
    filtered = client.get("/api/v1/admin/audit?action=puzzles.validate", headers=headers).json()
    assert len(filtered) == 1 and filtered[0]["target_id"] == str(pid)
