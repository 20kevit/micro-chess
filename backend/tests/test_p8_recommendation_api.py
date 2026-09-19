"""P8 — Recommendation API integration.

Thin HTTP coverage over the read-only P7 engine (which is NOT rebuilt
here): auth, stable shape, no ``trace`` leak, empty-catalog null,
determinism, and direct-assignment priority preserved through the API.
"""

from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import STATUS_PUBLISHED, Puzzle
from app.modules.relationships import service as relationship_service
from app.modules.users.models import User, UserRole

SLUG = "captures"
OTHER = "undefended-pieces"


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _ensure_exercise(db_session, slug):
    row = db_session.get(Exercise, slug)
    if row is None:
        row = Exercise(slug=slug, title_fa=slug, title_en=slug, is_active=True, sort_order=0)
        db_session.add(row)
        db_session.commit()
    return row


def _puzzle(db_session, slug, rating=1200.0):
    _ensure_exercise(db_session, slug)
    row = Puzzle(
        exercise_slug=slug,
        fen=None,
        position_json={},
        answer_json={"squares": ["e4"]},
        hint_json={},
        prompt_fa="",
        explanation="",
        initial_rating=rating,
        is_published=True,
        is_archived=False,
        status=STATUS_PUBLISHED,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _grant(db_session, username, role):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, role)) is None:
        db_session.add(UserRole(user_id=user.id, role=role))
        db_session.commit()
    return user


def test_requires_authentication(client):
    assert client.get("/api/v1/me/recommendations").status_code == 401


def test_empty_catalog_returns_null(client, db_session):
    token = _token(client, "rec_empty")
    res = client.get("/api/v1/me/recommendations", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json() is None


def test_cold_start_shape_and_no_trace_leak(client, db_session):
    token = _token(client, "rec_cold")
    puzzle = _puzzle(db_session, SLUG)
    res = client.get("/api/v1/me/recommendations", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body.keys()) == {"exercise_slug", "puzzle_id", "reason", "assignment_id"}
    assert body["exercise_slug"] == SLUG
    assert body["puzzle_id"] == puzzle.id
    assert body["reason"] == "COLD_START"
    assert body["assignment_id"] is None
    assert "trace" not in body


def test_deterministic_read_only_across_calls(client, db_session):
    token = _token(client, "rec_det")
    _puzzle(db_session, SLUG)
    first = client.get("/api/v1/me/recommendations", headers=_bearer(token)).json()
    second = client.get("/api/v1/me/recommendations", headers=_bearer(token)).json()
    assert first == second


def test_direct_assignment_priority_preserved(client, db_session):
    coach_token = _token(client, "rec_coach")
    student_token = _token(client, "rec_student")
    _grant(db_session, "rec_coach", "COACH")
    _puzzle(db_session, SLUG)
    assigned_puzzle = _puzzle(db_session, OTHER)
    coach = db_session.query(User).filter(User.username == "rec_coach").one()
    student = db_session.query(User).filter(User.username == "rec_student").one()
    rel = relationship_service.create_relationship(
        db_session, actor=coach, kind="coach", other_username=student.username
    )
    relationship_service.accept_relationship(db_session, actor=student, relationship_id=rel.id)
    row = relationship_service.create_assignment(
        db_session, coach=coach, student_id=student.id, exercise_slug=OTHER, note="drill"
    )
    res = client.get("/api/v1/me/recommendations", headers=_bearer(student_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exercise_slug"] == OTHER
    assert body["puzzle_id"] == assigned_puzzle.id
    assert body["reason"] == "DIRECT_ASSIGNMENT"
    assert body["assignment_id"] == row.id
    # Coach's own recommendation is unaffected (per-user isolation).
    own = client.get("/api/v1/me/recommendations", headers=_bearer(coach_token))
    assert own.status_code == 200
