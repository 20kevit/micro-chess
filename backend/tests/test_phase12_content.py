"""Phase 12 content management: answer contracts, exercise creation,
preview validation, extended filters, edit demotion, bulk ops, quality,
learning, health, and authorization."""

from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client, db_session, username="the_admin"):
    from app.modules.users.models import User, UserRole

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


START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _seed_pin_draft(db_session, answer=None):
    from app.modules.puzzles import service as puzzle_service

    _seed_exercise(db_session, "pin")
    return puzzle_service.create_draft(
        db_session,
        exercise_slug="pin",
        fen=START_FEN,
        answer_json=answer if answer is not None else {"fen": START_FEN, "pin": ["a1", "a2", "a3"]},
        prompt_fa="سوال",
    )


# --- answer contracts ----------------------------------------------------------


def test_answer_contract_for_known_exercise(client, db_session):
    token = _admin_token(client, db_session)
    res = client.get("/api/v1/admin/exercises/pin/answer-contract", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exercise_slug"] == "pin"
    assert body["answer_type"] == "ordered_squares"
    assert body["validator_registered"] is True
    assert isinstance(body["answer_fields"], list) and body["answer_fields"]


def test_answer_contract_unknown_slug_is_404(client, db_session):
    token = _admin_token(client, db_session)
    res = client.get(
        "/api/v1/admin/exercises/no-such-exercise/answer-contract", headers=_bearer(token)
    )
    assert res.status_code == 404


def test_answer_contract_requires_admin(client, db_session):
    _seed_exercise(db_session)
    token = _register(client).json()["access_token"]
    res = client.get("/api/v1/admin/exercises/pin/answer-contract", headers=_bearer(token))
    assert res.status_code == 403


# --- exercise creation -----------------------------------------------------------


def test_create_exercise_registered_slug(client, db_session):
    token = _admin_token(client, db_session)
    res = client.post(
        "/api/v1/admin/exercises",
        json={"slug": "pin", "title_fa": "آچمز"},
        headers=_bearer(token),
    )
    assert res.status_code == 201, res.text
    assert res.json()["slug"] == "pin"
    assert db_session.get(Exercise, "pin") is not None


def test_create_exercise_unregistered_slug_refused(client, db_session):
    token = _admin_token(client, db_session)
    res = client.post(
        "/api/v1/admin/exercises",
        json={"slug": "imaginary-exercise", "title_fa": "خیالی"},
        headers=_bearer(token),
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "exercise_not_implemented"
    assert db_session.get(Exercise, "imaginary-exercise") is None


def test_create_exercise_duplicate_conflicts(client, db_session):
    token = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    res = client.post(
        "/api/v1/admin/exercises",
        json={"slug": "pin", "title_fa": "آچمز"},
        headers=_bearer(token),
    )
    assert res.status_code == 409


def test_create_exercise_requires_capability(client, db_session):
    token = _register(client).json()["access_token"]
    res = client.post(
        "/api/v1/admin/exercises",
        json={"slug": "pin", "title_fa": "آچمز"},
        headers=_bearer(token),
    )
    assert res.status_code == 403


# --- preview validation ------------------------------------------------------------


def test_preview_validate_ok_writes_nothing(client, db_session):
    token = _admin_token(client, db_session)
    before = db_session.query(Puzzle).count()
    res = client.post(
        "/api/v1/admin/puzzles/preview-validate",
        json={
            "exercise_slug": "pin",
            "fen": START_FEN,
            "answer_json": {"fen": START_FEN, "pin": ["a1", "a2", "a3"]},
        },
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    # Generic gates pass for this shape (no pin-specific content hook);
    # the derived-answer replay may flag it — either way no row is written.
    assert db_session.query(Puzzle).count() == before


def test_preview_validate_accepts_modern_answer_contract_without_writes(client, db_session):
    token = _admin_token(client, db_session)
    before = db_session.query(Puzzle).count()
    response = client.post(
        "/api/v1/admin/puzzles/preview-validate",
        json={
            "exercise_slug": "piece-recognition",
            "fen": START_FEN,
            "position_json": {"target": "white-pawn"},
            "answer_json": {
                "squares": ["a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2"],
                "target": "white-pawn",
            },
        },
        headers=_bearer(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert body["content_hash"]
    assert db_session.query(Puzzle).count() == before


def test_preview_validate_bad_fen_fails(client, db_session):
    token = _admin_token(client, db_session)
    res = client.post(
        "/api/v1/admin/puzzles/preview-validate",
        json={"exercise_slug": "pin", "fen": "not-a-fen", "answer_json": {"pin": ["a1"]}},
        headers=_bearer(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(e["code"] == "invalid_fen" for e in body["errors"])


def test_preview_validate_requires_admin(client, db_session):
    token = _register(client).json()["access_token"]
    res = client.post(
        "/api/v1/admin/puzzles/preview-validate",
        json={"exercise_slug": "pin", "answer_json": {}},
        headers=_bearer(token),
    )
    assert res.status_code == 403


# --- extended puzzle filters ---------------------------------------------------------


def test_puzzle_list_filters_and_sort(client, db_session):
    from app.modules.puzzles import service as puzzle_service

    token = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    easy = puzzle_service.create_draft(
        db_session, exercise_slug="pin", fen=START_FEN,
        answer_json={"fen": START_FEN, "pin": ["a1"]},
        prompt_fa="سوال آسان", difficulty=1, initial_rating=800.0,
    )
    hard = puzzle_service.create_draft(
        db_session, exercise_slug="pin", fen=START_FEN,
        answer_json={"fen": START_FEN, "pin": ["b1"]},
        prompt_fa="سوال سخت", difficulty=5, initial_rating=2000.0,
    )
    _ = easy, hard

    res = client.get("/api/v1/admin/puzzles?difficulty=5", headers=_bearer(token))
    assert res.status_code == 200
    rows = res.json()
    assert rows and all(r["difficulty"] == 5 for r in rows)

    res = client.get("/api/v1/admin/puzzles?search=سخت", headers=_bearer(token))
    assert res.status_code == 200
    assert any("سخت" in r["prompt_fa"] for r in res.json())

    res = client.get(
        "/api/v1/admin/puzzles?rating_min=1500&sort=initial_rating&order=desc",
        headers=_bearer(token),
    )
    assert res.status_code == 200
    rows = res.json()
    assert rows and all(r["initial_rating"] >= 1500 for r in rows)
    ratings = [r["initial_rating"] for r in rows]
    assert ratings == sorted(ratings, reverse=True)


def test_puzzle_list_invalid_filter_rejected(client, db_session):
    token = _admin_token(client, db_session)
    assert (
        client.get("/api/v1/admin/puzzles?difficulty=9", headers=_bearer(token)).status_code
        == 422
    )
    assert (
        client.get("/api/v1/admin/puzzles?sort=nope", headers=_bearer(token)).status_code == 422
    )


# --- edit demotion ---------------------------------------------------------------------


def test_editing_validated_content_demotes_to_draft(client, db_session):
    from app.modules.admin import service as admin_service

    token = _admin_token(client, db_session)
    puzzle = _seed_pin_draft(db_session)
    admin_service.validate_puzzle(db_session, actor_id=1, puzzle_id=puzzle.id)
    assert db_session.get(Puzzle, puzzle.id).status == "validated"

    res = client.patch(
        f"/api/v1/admin/puzzles/{puzzle.id}",
        json={"answer_json": {"fen": START_FEN, "pin": ["c1", "c2", "c3"]}},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    row = db_session.get(Puzzle, puzzle.id)
    assert row.status == "draft"
    assert row.answer_json["pin"] == ["c1", "c2", "c3"]
    history = admin_service.puzzle_history(db_session, puzzle.id)
    assert history["transitions"][-1]["to_status"] == "draft"


def test_editing_published_answer_stays_locked(client, db_session):
    from app.modules.puzzles import service as puzzle_service

    token = _admin_token(client, db_session)
    puzzle = _seed_pin_draft(db_session)
    puzzle_service.publish(db_session, puzzle)
    res = client.patch(
        f"/api/v1/admin/puzzles/{puzzle.id}",
        json={"answer_json": {"fen": START_FEN, "pin": ["x"]}},
        headers=_bearer(token),
    )
    assert res.status_code == 409


# --- bulk operations ---------------------------------------------------------------------


def _publishable_draft(db_session):
    return _seed_pin_draft(db_session)


def test_bulk_validate_lifecycle_safe(client, db_session):
    from app.modules.admin import service as admin_service
    from app.modules.puzzles import service as puzzle_service

    token = _admin_token(client, db_session)
    good = _publishable_draft(db_session)
    # Published content cannot be (re)validated: invalid_transition.
    locked = _seed_pin_draft(db_session)
    puzzle_service.publish(db_session, locked)
    res = client.post(
        "/api/v1/admin/puzzles/bulk",
        json={"puzzle_ids": [good.id, locked.id, 999999], "action": "validate"},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert good.id in body["succeeded"]
    assert {f["id"] for f in body["failed"]} == {locked.id, 999999}
    assert db_session.get(Puzzle, good.id).status == "validated"
    _ = admin_service  # history/audit covered by single-item tests


def test_bulk_destructive_requires_reason(client, db_session):
    token = _admin_token(client, db_session)
    puzzle = _publishable_draft(db_session)
    res = client.post(
        "/api/v1/admin/puzzles/bulk",
        json={"puzzle_ids": [puzzle.id], "action": "retire", "reason": ""},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    res = client.post(
        "/api/v1/admin/puzzles/bulk",
        json={"puzzle_ids": [puzzle.id], "action": "retire", "reason": "محتوای تکراری"},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["succeeded"] == [puzzle.id]
    assert db_session.get(Puzzle, puzzle.id).status == "retired"


def test_bulk_requires_per_action_capability(client, db_session):
    token = _register(client).json()["access_token"]
    res = client.post(
        "/api/v1/admin/puzzles/bulk",
        json={"puzzle_ids": [1], "action": "publish"},
        headers=_bearer(token),
    )
    assert res.status_code == 403


# --- quality / learning / health / usage ---------------------------------------------------


def test_exercise_quality_reports_real_signals(client, db_session):
    token = _admin_token(client, db_session)
    _seed_pin_draft(db_session)
    res = client.get("/api/v1/admin/exercises/pin/quality", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exercise_slug"] == "pin"
    assert body["published"] == 0
    assert body["supply_state"] == "critical"
    assert "low_supply" in body["attention_reasons"]
    assert body["success_rate"] is None  # no attempts: null, never invented


def test_exercise_learning_shape(client, db_session):
    token = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    res = client.get("/api/v1/admin/exercises/pin/learning?days=30", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exercise_slug"] == "pin"
    assert body["skills"]["primary"] is not None  # canonical taxonomy mapping
    assert body["usage"]["attempts"] == 0


def test_content_health_lists_exercises(client, db_session):
    token = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    res = client.get("/api/v1/admin/content-health", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["attention_count"] >= 1
    pin_row = next(r for r in body["exercises"] if r["slug"] == "pin")
    assert pin_row["supply_state"] == "critical"
    assert "low_supply" in pin_row["reasons"]
    assert "generator_available" in pin_row


def test_puzzle_usage_counts(client, db_session):
    token = _admin_token(client, db_session)
    puzzle = _seed_pin_draft(db_session)
    res = client.get(f"/api/v1/admin/puzzles/{puzzle.id}/usage", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["puzzle_id"] == puzzle.id
    assert body["attempts"] == 0
    assert body["success_rate"] is None


def test_quality_unknown_exercise_is_404(client, db_session):
    token = _admin_token(client, db_session)
    assert (
        client.get("/api/v1/admin/exercises/nope/quality", headers=_bearer(token)).status_code
        == 404
    )
