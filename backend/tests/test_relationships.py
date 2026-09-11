"""Phase 9 relationships: lifecycle, object-level authorization, scope, audit.

Covers coach-student and parent-student edges (PENDING -> ACTIVE ->
REVOKED), the cross-user authorization matrix, secret-free data scope,
assignment foundation, audit records, and the v8 schema contract.
"""

from app.modules.admin.models import AuditLog
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.relationships.models import Assignment, Relationship
from app.modules.users.models import User, UserRole


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _grant(db_session, username, role):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, role)) is None:
        db_session.add(UserRole(user_id=user.id, role=role))
        db_session.commit()
    return user


def _user_id(client, token):
    return client.get("/api/v1/users/me", headers=_bearer(token)).json()["id"]


def _setup_coach_student(client, coach="coach_a", student="student_a"):
    coach_token = _token(client, coach)
    student_token = _token(client, student)
    return coach_token, student_token


def _invite(client, db_session, mentor, student, kind):
    mentor_token = _token(client, mentor)
    student_token = _token(client, student)
    _grant(db_session, mentor, "COACH" if kind == "coach" else "PARENT")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": kind, "other_username": student},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 201, res.text
    rel_id = res.json()["id"]
    assert res.json()["status"] == "pending"
    return mentor_token, student_token, rel_id


def _activate(client, mentor_token, student_token, rel_id):
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(student_token))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"
    return res.json()


def _seeded_piece_puzzle(db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG

    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def _correct(puzzle):
    return {"selected_squares": list(puzzle.answer_json["squares"])}


# --- lifecycle -----------------------------------------------------------------


def test_coach_invite_creates_pending_without_access(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    student_id = _user_id(client, student_token)
    # Pending grants nothing.
    res = client.get(f"/api/v1/coach/students/{student_id}/progress", headers=_bearer(mentor_token))
    assert res.status_code == 404
    res = client.get("/api/v1/coach/students", headers=_bearer(mentor_token))
    assert res.status_code == 200 and res.json() == []
    _activate(client, mentor_token, student_token, rel_id)
    res = client.get(f"/api/v1/coach/students/{student_id}/progress", headers=_bearer(mentor_token))
    assert res.status_code == 200
    assert res.json()["attempts"] == 0


def test_duplicate_invitation_rejected(client, db_session):
    mentor_token, student_token, _ = _invite(client, db_session, "coach_a", "student_a", "coach")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "student_a"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 409
    # Reverse direction while pending is the same edge: also rejected.
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "coach_a"},
        headers=_bearer(student_token),
    )
    assert res.status_code == 409


def test_self_unknown_kind_and_role_combination_rejected(client, db_session):
    token = _token(client, "lonely_coach")
    _grant(db_session, "lonely_coach", "COACH")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "lonely_coach"},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "ghost_user"},
        headers=_bearer(token),
    )
    assert res.status_code == 404
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "mentor", "other_username": "ghost_user"},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    # Two plain players cannot form a coach edge.
    plain_a = _token(client, "plain_a")
    _token(client, "plain_b")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "plain_b"},
        headers=_bearer(plain_a),
    )
    assert res.status_code == 422


def test_creator_cannot_accept_own_invitation(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(mentor_token))
    assert res.status_code == 403
    _activate(client, mentor_token, student_token, rel_id)


def test_accept_is_idempotent(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    _activate(client, mentor_token, student_token, rel_id)
    before = db_session.query(AuditLog).filter(AuditLog.action == "relationships.accept").count()
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(student_token))
    assert res.status_code == 200 and res.json()["status"] == "active"
    after = db_session.query(AuditLog).filter(AuditLog.action == "relationships.accept").count()
    assert after == before


def test_revoke_removes_access_and_is_idempotent(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    student_id = _user_id(client, student_token)
    _activate(client, mentor_token, student_token, rel_id)
    res = client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(student_token))
    assert res.status_code == 200 and res.json()["status"] == "revoked"
    for path in (
        f"/api/v1/coach/students/{student_id}/progress",
        f"/api/v1/coach/students/{student_id}/ratings",
        f"/api/v1/coach/students/{student_id}/analytics",
    ):
        assert client.get(path, headers=_bearer(mentor_token)).status_code == 404, path
    assert client.get("/api/v1/coach/students", headers=_bearer(mentor_token)).json() == []
    # Accept after revoke is an invalid transition.
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(student_token))
    assert res.status_code == 409
    # Revoke again is a no-op.
    res = client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(mentor_token))
    assert res.status_code == 200 and res.json()["status"] == "revoked"


def test_revoked_edge_allows_fresh_invitation_with_history_preserved(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    _activate(client, mentor_token, student_token, rel_id)
    client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(mentor_token))
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "student_a"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 201
    assert res.json()["id"] != rel_id
    assert res.json()["status"] == "pending"
    rows = db_session.query(Relationship).filter(Relationship.mentor_user_id == _user_id(client, mentor_token)).all()
    assert len(rows) == 2


def test_student_initiated_flow_mentor_accepts(client, db_session):
    coach_token = _token(client, "coach_b")
    student_token = _token(client, "student_b")
    _grant(db_session, "coach_b", "COACH")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "coach_b"},
        headers=_bearer(student_token),
    )
    assert res.status_code == 201
    rel_id = res.json()["id"]
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(coach_token))
    assert res.status_code == 200 and res.json()["status"] == "active"


def test_inactive_account_blocks_creation_and_acceptance(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    student = db_session.query(User).filter(User.username == "student_a").one()
    student.is_active = False
    db_session.commit()
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(student_token))
    # Suspended sessions fail closed at authentication.
    assert res.status_code in (401, 409)
    student.is_active = True
    db_session.commit()
    _activate(client, mentor_token, student_token, rel_id)


def test_parent_flow_with_multiple_children_isolated(client, db_session):
    parent_token, child_a_token, rel_a = _invite(client, db_session, "parent_a", "child_a", "parent")
    _token(client, "child_b")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "parent", "other_username": "child_b"},
        headers=_bearer(parent_token),
    )
    assert res.status_code == 201
    rel_b = res.json()["id"]
    # Log in as child_b (registration tokens are single-use here).
    login = client.post("/api/v1/auth/login", json={"username": "child_b", "password": "secret123"})
    child_b_token = login.json()["access_token"]
    _activate(client, parent_token, child_a_token, rel_a)
    child_a_id = _user_id(client, child_a_token)
    child_b_id = _user_id(client, child_b_token)
    assert client.get(f"/api/v1/parent/children/{child_a_id}/progress", headers=_bearer(parent_token)).status_code == 200
    # Pending child_b grants nothing yet.
    assert client.get(f"/api/v1/parent/children/{child_b_id}/progress", headers=_bearer(parent_token)).status_code == 404
    children = client.get("/api/v1/parent/children", headers=_bearer(parent_token)).json()
    assert [c["id"] for c in children] == [child_a_id]
    _activate(client, parent_token, child_b_token, rel_b)
    children = client.get("/api/v1/parent/children", headers=_bearer(parent_token)).json()
    assert sorted(c["id"] for c in children) == sorted([child_a_id, child_b_id])


def test_coach_and_parent_permissions_stay_separate(client, db_session):
    coach_token, student_token, coach_rel = _invite(client, db_session, "coach_a", "student_a", "coach")
    parent_token = _token(client, "parent_a")
    _grant(db_session, "parent_a", "PARENT")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": "parent", "other_username": "student_a"},
        headers=_bearer(parent_token),
    )
    parent_rel = res.json()["id"]
    _activate(client, coach_token, student_token, coach_rel)
    student_id = _user_id(client, student_token)
    # Coach edge does not authorize parent endpoints and vice versa.
    assert client.get(f"/api/v1/parent/children/{student_id}/progress", headers=_bearer(coach_token)).status_code == 404
    assert client.get(f"/api/v1/coach/students/{student_id}/progress", headers=_bearer(parent_token)).status_code == 404
    # Parent edge pending: parent reads still denied.
    assert client.get(f"/api/v1/parent/children/{student_id}/progress", headers=_bearer(parent_token)).status_code == 404
    _activate(client, parent_token, student_token, parent_rel)
    assert client.get(f"/api/v1/parent/children/{student_id}/progress", headers=_bearer(parent_token)).status_code == 200
    assert client.get(f"/api/v1/coach/students/{student_id}/progress", headers=_bearer(coach_token)).status_code == 200


# --- authorization matrix --------------------------------------------------------


def _matrix(client, db_session):
    """Student A linked to coach A + parent A; student B linked to nobody."""
    coach_a, student_a, rel_c = _invite(client, db_session, "coach_a", "student_a", "coach")
    parent_a = _token(client, "parent_a")
    _grant(db_session, "parent_a", "PARENT")
    res = client.post(
        "/api/v1/relationships", json={"kind": "parent", "other_username": "student_a"},
        headers=_bearer(parent_a),
    )
    rel_p = res.json()["id"]
    _activate(client, coach_a, student_a, rel_c)
    _activate(client, parent_a, student_a, rel_p)
    coach_b = _token(client, "coach_b")
    _grant(db_session, "coach_b", "COACH")
    parent_b = _token(client, "parent_b")
    _grant(db_session, "parent_b", "PARENT")
    student_b = _token(client, "student_b")
    admin = _token(client, "admin_x")
    _grant(db_session, "admin_x", "ADMIN")
    return {
        "coach_a": coach_a, "parent_a": parent_a, "student_a": student_a,
        "coach_b": coach_b, "parent_b": parent_b, "student_b": student_b,
        "admin": admin,
        "student_a_id": _user_id(client, student_a),
        "student_b_id": _user_id(client, student_b),
    }


def test_authorization_matrix_reads(client, db_session):
    m = _matrix(client, db_session)
    paths_a = [
        f"/api/v1/coach/students/{m['student_a_id']}",
        f"/api/v1/coach/students/{m['student_a_id']}/progress",
        f"/api/v1/coach/students/{m['student_a_id']}/attempts",
        f"/api/v1/coach/students/{m['student_a_id']}/ratings",
        f"/api/v1/coach/students/{m['student_a_id']}/gamification",
        f"/api/v1/coach/students/{m['student_a_id']}/achievements",
        f"/api/v1/coach/students/{m['student_a_id']}/analytics",
    ]
    for path in paths_a:
        assert client.get(path, headers=_bearer(m["coach_a"])).status_code == 200, path
    # Coach A cannot touch student B (direct guessed id).
    for path in (p.replace(str(m["student_a_id"]), str(m["student_b_id"])) for p in paths_a):
        assert client.get(path, headers=_bearer(m["coach_a"])).status_code == 404, path
    # Unrelated coach B / parent B denied on student A.
    assert client.get(paths_a[1], headers=_bearer(m["coach_b"])).status_code == 404
    assert client.get(
        f"/api/v1/parent/children/{m['student_a_id']}/progress", headers=_bearer(m["parent_b"])
    ).status_code == 404
    # Parent A allowed on own child, denied on student B.
    assert client.get(
        f"/api/v1/parent/children/{m['student_a_id']}/progress", headers=_bearer(m["parent_a"])
    ).status_code == 200
    assert client.get(
        f"/api/v1/parent/children/{m['student_b_id']}/progress", headers=_bearer(m["parent_a"])
    ).status_code == 404
    # Student keeps own access; anonymous is rejected; admin has no edge access.
    assert client.get("/api/v1/me/progress", headers=_bearer(m["student_a"])).status_code == 200
    assert client.get(paths_a[1]).status_code == 401
    assert client.get(paths_a[1], headers=_bearer(m["admin"])).status_code == 404
    # Normal player cannot read another student through mentor routes.
    assert client.get(paths_a[1], headers=_bearer(m["student_b"])).status_code == 404


def test_relationship_management_is_party_scoped(client, db_session):
    m = _matrix(client, db_session)
    res = client.get("/api/v1/relationships", headers=_bearer(m["coach_a"]))
    assert res.status_code == 200 and len(res.json()) == 1
    rel_id = res.json()[0]["id"]
    # Outsiders cannot view or revoke the edge.
    assert client.get(f"/api/v1/relationships/{rel_id}", headers=_bearer(m["coach_b"])).status_code == 404
    assert client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(m["coach_b"])).status_code == 404
    assert client.get(f"/api/v1/relationships/{rel_id}").status_code == 401
    # Lists never include foreign edges.
    assert client.get("/api/v1/relationships", headers=_bearer(m["student_b"])).json() == []


# --- data scope -------------------------------------------------------------------


def test_related_student_views_are_secret_free(client, db_session):
    m = _matrix(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    submit = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": _correct(puzzle), "mode": "practice"},
        headers=_bearer(m["student_a"]),
    )
    assert submit.status_code == 200, submit.text
    attempt_id = submit.json()["id"]
    identity = client.get(
        f"/api/v1/coach/students/{m['student_a_id']}", headers=_bearer(m["coach_a"])
    ).json()
    assert set(identity.keys()) == {"id", "username", "display_name"}
    body = client.get(
        f"/api/v1/coach/students/{m['student_a_id']}/attempts", headers=_bearer(m["coach_a"])
    ).json()
    assert len(body) == 1 and body[0]["id"] == attempt_id
    assert "answer_json" not in body[0]
    detail = client.get(
        f"/api/v1/coach/students/{m['student_a_id']}/attempts/{attempt_id}",
        headers=_bearer(m["coach_a"]),
    ).json()
    assert "answer_json" not in detail
    forbidden = ("password_hash", "password", "token", "session", "email", "answer_json")
    for payload in (
        identity, body[0], detail,
        client.get(f"/api/v1/coach/students/{m['student_a_id']}/progress", headers=_bearer(m["coach_a"])).json(),
        client.get(f"/api/v1/coach/students/{m['student_a_id']}/ratings", headers=_bearer(m["coach_a"])).json(),
        client.get(f"/api/v1/coach/students/{m['student_a_id']}/gamification", headers=_bearer(m["coach_a"])).json(),
        client.get(f"/api/v1/coach/students/{m['student_a_id']}/analytics", headers=_bearer(m["coach_a"])).json(),
    ):
        text = str(payload).lower()
        for secret in forbidden:
            assert secret not in text, secret
    # Foreign attempt ids stay invisible even when the student id is authorized.
    other = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": _correct(puzzle), "mode": "practice"},
        headers=_bearer(m["student_b"]),
    ).json()["id"]
    res = client.get(
        f"/api/v1/coach/students/{m['student_a_id']}/attempts/{other}", headers=_bearer(m["coach_a"])
    )
    assert res.status_code == 404


def test_relationship_analytics_match_student_own_view(client, db_session):
    m = _matrix(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    for _ in range(2):
        client.post(
            "/api/v1/attempts",
            json={"puzzle_id": puzzle.id, "answer": _correct(puzzle), "mode": "practice"},
            headers=_bearer(m["student_a"]),
        )
    own = client.get("/api/v1/me/analytics?period=all", headers=_bearer(m["student_a"])).json()
    scoped = client.get(
        f"/api/v1/coach/students/{m['student_a_id']}/analytics?period=all",
        headers=_bearer(m["coach_a"]),
    ).json()
    assert scoped["totals"]["attempts"] == own["totals"]["attempts"] == 2
    assert scoped["totals"]["accuracy"] == own["totals"]["accuracy"] == 1.0


# --- assignments ---------------------------------------------------------------------


def test_assignment_foundation_requires_active_relationship(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    student_id = _user_id(client, student_token)
    puzzle = _seeded_piece_puzzle(db_session)
    slug = puzzle.exercise_slug
    # Pending: blocked.
    res = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student_id, "exercise_slug": slug, "note": "practice set"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 403
    _activate(client, mentor_token, student_token, rel_id)
    res = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student_id, "exercise_slug": slug, "note": "practice set"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 201, res.text
    assignment_id = res.json()["id"]
    assert res.json()["status"] == "assigned"
    # Unknown exercise rejected; unrelated student rejected.
    res = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student_id, "exercise_slug": "nope"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 404
    stranger = _token(client, "stranger")
    stranger_id = _user_id(client, stranger)
    res = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": stranger_id, "exercise_slug": slug},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 403
    # Coach list + student own list.
    assert len(client.get("/api/v1/coach/assignments", headers=_bearer(mentor_token)).json()) == 1
    own = client.get("/api/v1/me/assignments", headers=_bearer(student_token)).json()
    assert len(own) == 1 and own[0]["exercise_slug"] == slug
    # Student completes; terminal states never reopen.
    res = client.patch(
        f"/api/v1/me/assignments/{assignment_id}", json={"status": "completed"},
        headers=_bearer(student_token),
    )
    assert res.status_code == 200 and res.json()["status"] == "completed"
    res = client.patch(
        f"/api/v1/coach/assignments/{assignment_id}", json={"status": "assigned"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 409
    # Student cannot cancel.
    second = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student_id, "exercise_slug": slug},
        headers=_bearer(mentor_token),
    ).json()["id"]
    res = client.patch(
        f"/api/v1/me/assignments/{second}", json={"status": "cancelled"},
        headers=_bearer(student_token),
    )
    assert res.status_code == 403
    res = client.patch(
        f"/api/v1/coach/assignments/{second}", json={"status": "cancelled"},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 200
    # History untouched by assignment work.
    assert db_session.query(Attempt).count() == 0
    # Revocation blocks new assignments but keeps old rows readable.
    client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(mentor_token))
    res = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student_id, "exercise_slug": slug},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 403
    assert len(client.get("/api/v1/me/assignments", headers=_bearer(student_token)).json()) == 2


def test_parent_sees_child_assignments_read_only(client, db_session):
    m = _matrix(client, db_session)
    puzzle = _seeded_piece_puzzle(db_session)
    created = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": m["student_a_id"], "exercise_slug": puzzle.exercise_slug, "note": "daily set"},
        headers=_bearer(m["coach_a"]),
    )
    assert created.status_code == 201, created.text
    rows = client.get(
        f"/api/v1/parent/children/{m['student_a_id']}/assignments", headers=_bearer(m["parent_a"])
    )
    assert rows.status_code == 200 and len(rows.json()) == 1
    assert rows.json()[0]["note"] == "daily set"
    # Unrelated parent and unrelated student stay invisible.
    assert client.get(
        f"/api/v1/parent/children/{m['student_a_id']}/assignments", headers=_bearer(m["parent_b"])
    ).status_code == 404
    assert client.get(
        f"/api/v1/parent/children/{m['student_b_id']}/assignments", headers=_bearer(m["parent_a"])
    ).status_code == 404
    # Parents cannot create or modify assignments.
    assert client.post(
        "/api/v1/coach/assignments",
        json={"student_id": m["student_a_id"], "exercise_slug": puzzle.exercise_slug},
        headers=_bearer(m["parent_a"]),
    ).status_code == 403


# --- audit ---------------------------------------------------------------------------


def test_relationship_transitions_are_audited_but_reads_are_not(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    student_id = _user_id(client, student_token)
    _activate(client, mentor_token, student_token, rel_id)
    client.get(f"/api/v1/coach/students/{student_id}/progress", headers=_bearer(mentor_token))
    client.get("/api/v1/coach/students", headers=_bearer(mentor_token))
    client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(mentor_token))
    actions = [row.action for row in db_session.query(AuditLog).order_by(AuditLog.id).all()]
    assert "relationships.create" in actions
    assert "relationships.accept" in actions
    assert "relationships.revoke" in actions
    for row in db_session.query(AuditLog).all():
        assert row.target_type in ("relationship", "assignment", "user")
        assert "password" not in str(row.metadata_json).lower()
        assert "token" not in str(row.metadata_json).lower()


# --- migration --------------------------------------------------------------------------


def test_v8_upgrade_preserves_data_and_is_idempotent(client, db_session):
    from sqlalchemy import inspect

    from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version

    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_a", "student_a", "coach")
    _activate(client, mentor_token, student_token, rel_id)
    engine = db_session.bind
    assert get_schema_version(engine) is None or get_schema_version(engine) == SCHEMA_VERSION
    tables = inspect(engine).get_table_names()
    assert "relationships" in tables and "assignments" in tables
    rel_rows = db_session.query(Relationship).count()
    user_rows = db_session.query(User).count()
    assert db_session.query(Assignment).count() == 0
    assert ensure_schema(engine) == 10
    assert db_session.query(Relationship).count() == rel_rows
    assert db_session.query(User).count() == user_rows
