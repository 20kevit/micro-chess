"""Phase 6 administration: authorization, users, exercises, puzzles, audit."""

from app.modules.admin.models import AuditLog
from app.modules.exercises.models import Exercise
from app.modules.puzzles.models import Puzzle
from app.modules.users.models import User, UserRole


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _login(client, username="player_one", password="secret123"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


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


def _seed_puzzle(db_session, slug="pin", answer=None, published=True):
    from app.modules.puzzles import service as puzzle_service

    _seed_exercise(db_session, slug)
    puzzle = puzzle_service.create_draft(
        db_session,
        exercise_slug=slug,
        answer_json=answer if answer is not None else {"moves": ["e2e4"]},
        prompt_fa="سوال",
    )
    if published:
        puzzle_service.publish(db_session, puzzle)
    return puzzle


# --- authorization ----------------------------------------------------------


def test_anonymous_admin_access_is_401(client):
    assert client.get("/api/v1/admin/dashboard").status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.post("/api/v1/admin/puzzles", json={}).status_code == 401


def test_player_admin_access_is_denied(client):
    token = _register(client).json()["access_token"]
    headers = _bearer(token)
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/exercises", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/puzzles", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=headers).status_code == 403


def test_coach_and_parent_have_no_admin_access(client, db_session):
    token = _register(client, username="coach_one").json()["access_token"]
    user = db_session.query(User).filter(User.username == "coach_one").one()
    db_session.add(UserRole(user_id=user.id, role="COACH"))
    db_session.add(UserRole(user_id=user.id, role="PARENT"))
    db_session.commit()
    headers = _bearer(token)
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403


def test_admin_can_access_overview(client, db_session):
    token = _admin_token(client, db_session)
    res = client.get("/api/v1/admin/dashboard", headers=_bearer(token))
    assert res.status_code == 200
    body = res.json()
    assert body["users_total"] >= 1
    assert "password" not in str(body).lower()


def test_frontend_role_spoof_is_ineffective(client, db_session):
    # Client-supplied role claims are ignored at registration and in JWTs.
    res = _register(client, username="sneaky", roles=["ADMIN"], is_admin=True)
    assert res.status_code == 201
    me = client.get("/api/v1/users/me", headers=_bearer(res.json()["access_token"]))
    assert me.json()["roles"] == ["PLAYER"]
    sneaky = client.get("/api/v1/admin/dashboard", headers=_bearer(res.json()["access_token"]))
    assert sneaky.status_code == 403


def test_player_cannot_reach_admin_puzzle_answers(client, db_session):
    puzzle = _seed_puzzle(db_session)
    token = _register(client, username="regular").json()["access_token"]
    res = client.get(f"/api/v1/admin/puzzles/{puzzle.id}", headers=_bearer(token))
    assert res.status_code == 403
    # Player-visible shape still hides the answer.
    visible = client.get(f"/api/v1/puzzles/{puzzle.id}", headers=_bearer(token))
    assert visible.status_code == 200
    assert "answer_json" not in visible.json()


# --- overview ----------------------------------------------------------------


def test_overview_counts_and_no_secrets(client, db_session):
    admin = _admin_token(client, db_session)
    _register(client, username="second")
    _seed_puzzle(db_session)
    res = client.get("/api/v1/admin/dashboard", headers=_bearer(admin))
    assert res.status_code == 200
    body = res.json()
    assert body["users_total"] == 2  # the_admin + second
    assert body["users_total"] >= body["users_active"]
    assert body["users_suspended"] == body["users_total"] - body["users_active"]
    assert body["puzzles_total"] >= 1
    assert body["puzzles_published"] >= 1
    assert body["exercises_total"] >= 1
    assert isinstance(body["recent_registrations"], list)
    assert isinstance(body["recent_audit"], list)
    flat = str(body).lower()
    assert "password_hash" not in flat
    assert "token_hash" not in flat
    assert "access_token" not in flat


# --- user management ----------------------------------------------------------


def test_admin_user_list_search_filter_pagination(client, db_session):
    admin = _admin_token(client, db_session)
    _register(client, username="alice_one")
    _register(client, username="bob_two")
    headers = _bearer(admin)

    all_users = client.get("/api/v1/admin/users", headers=headers)
    assert all_users.status_code == 200
    assert len(all_users.json()) >= 3

    search = client.get("/api/v1/admin/users?search=alice", headers=headers)
    assert [u["username"] for u in search.json()] == ["alice_one"]

    by_role = client.get("/api/v1/admin/users?role=ADMIN", headers=headers)
    assert {u["username"] for u in by_role.json()} == {"the_admin"}

    by_status = client.get("/api/v1/admin/users?status=active", headers=headers)
    assert len(by_status.json()) >= 3

    assert client.get("/api/v1/admin/users?role=NOPE", headers=headers).status_code == 422
    assert client.get("/api/v1/admin/users?page_size=201", headers=headers).status_code == 422
    assert client.get("/api/v1/admin/users?sort=nope", headers=headers).status_code == 422


def test_admin_user_detail_shape_and_404(client, db_session):
    admin = _admin_token(client, db_session)
    user = db_session.query(User).filter(User.username == "the_admin").one()
    res = client.get(f"/api/v1/admin/users/{user.id}", headers=_bearer(admin))
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"id", "username", "display_name", "roles", "is_active", "created_at",
                         "profile", "attempts_count"}
    assert "password_hash" not in body
    assert "email" not in body
    assert "token" not in str(body).lower()
    assert client.get("/api/v1/admin/users/999999", headers=_bearer(admin)).status_code == 404


def test_suspend_and_reactivate_flow(client, db_session):
    admin_token = _admin_token(client, db_session)
    target_token = _register(client, username="target_one").json()["access_token"]
    target = db_session.query(User).filter(User.username == "target_one").one()
    headers = _bearer(admin_token)

    suspended = client.post(f"/api/v1/admin/users/{target.id}/suspend", headers=headers)
    assert suspended.status_code == 200
    assert suspended.json()["is_active"] is False
    # Suspended account: generic login failure + live token dies.
    assert _login(client, username="target_one").status_code == 401
    assert client.get("/api/v1/users/me", headers=_bearer(target_token)).status_code == 401

    # Repeat suspension is idempotent.
    again = client.post(f"/api/v1/admin/users/{target.id}/suspend", headers=headers)
    assert again.status_code == 200
    assert again.json()["is_active"] is False

    reactivated = client.post(f"/api/v1/admin/users/{target.id}/reactivate", headers=headers)
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert _login(client, username="target_one").status_code == 200

    # Repeat reactivation is idempotent.
    assert client.post(f"/api/v1/admin/users/{target.id}/reactivate", headers=headers).status_code == 200
    assert client.post("/api/v1/admin/users/999999/suspend", headers=headers).status_code == 404

    audits = db_session.query(AuditLog).filter(AuditLog.action == "users.suspend").all()
    assert len(audits) == 1
    assert audits[0].actor_user_id == db_session.query(User).filter(User.username == "the_admin").one().id
    assert audits[0].target_id == str(target.id)


def test_player_cannot_suspend(client, db_session):
    _admin_token(client, db_session)
    player = _register(client, username="plain").json()["access_token"]
    victim = db_session.query(User).filter(User.username == "the_admin").one()
    res = client.post(f"/api/v1/admin/users/{victim.id}/suspend", headers=_bearer(player))
    assert res.status_code == 403
    db_session.refresh(victim)
    assert victim.is_active is True


# --- roles ---------------------------------------------------------------------


def test_role_assign_revoke_and_persistence(client, db_session):
    admin_token = _admin_token(client, db_session)
    _register(client, username="future_coach")
    target = db_session.query(User).filter(User.username == "future_coach").one()
    headers = _bearer(admin_token)

    roles = client.get(f"/api/v1/admin/users/{target.id}/roles", headers=headers)
    assert roles.json() == {"roles": ["PLAYER"]}

    assigned = client.post(f"/api/v1/admin/users/{target.id}/roles", json={"role": "COACH"}, headers=headers)
    assert assigned.status_code == 200
    assert assigned.json() == {"roles": ["PLAYER", "COACH"]}

    # Idempotent re-assignment.
    assert client.post(f"/api/v1/admin/users/{target.id}/roles", json={"role": "COACH"}, headers=headers).status_code == 200
    db_session.refresh(target)
    assert sorted(r.role for r in target.roles) == ["COACH", "PLAYER"]

    assert client.post(f"/api/v1/admin/users/{target.id}/roles", json={"role": "WIZARD"}, headers=headers).status_code == 422
    assert client.post("/api/v1/admin/users/999999/roles", json={"role": "COACH"}, headers=headers).status_code == 404

    revoked = client.delete(f"/api/v1/admin/users/{target.id}/roles/COACH", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json() == {"roles": ["PLAYER"]}


def test_last_admin_is_protected(client, db_session):
    admin_token = _admin_token(client, db_session)
    admin = db_session.query(User).filter(User.username == "the_admin").one()
    headers = _bearer(admin_token)
    res = client.delete(f"/api/v1/admin/users/{admin.id}/roles/ADMIN", headers=headers)
    assert res.status_code == 409
    db_session.refresh(admin)
    assert "ADMIN" in [r.role for r in admin.roles]

    # With a second admin present, revocation succeeds.
    _register(client, username="second_admin")
    second = db_session.query(User).filter(User.username == "second_admin").one()
    db_session.add(UserRole(user_id=second.id, role="ADMIN"))
    db_session.commit()
    # The pre-promotion session stays PLAYER-active; the second admin
    # acts through a fresh ADMIN-active session.
    second_token = client.post(
        "/api/v1/auth/login",
        json={"username": "second_admin", "password": "secret123", "role": "ADMIN"},
    ).json()["access_token"]
    res = client.delete(f"/api/v1/admin/users/{admin.id}/roles/ADMIN", headers=_bearer(second_token))
    assert res.status_code == 200
    assert res.json() == {"roles": ["PLAYER"]}
    # The demoted admin's live session dies entirely (its active role is
    # no longer assigned, so it authorizes as nothing): fail closed with
    # 401, forcing a fresh login that picks a still-assigned role.
    demoted = client.get("/api/v1/admin/dashboard", headers=headers)
    assert demoted.status_code == 401
    assert demoted.json()["error"]["code"] == "ACTIVE_ROLE_REVOKED"


def test_promoted_admin_gains_access(client, db_session):
    admin_token = _admin_token(client, db_session)
    token = _register(client, username="rising").json()["access_token"]
    rising = db_session.query(User).filter(User.username == "rising").one()
    assert client.get("/api/v1/admin/dashboard", headers=_bearer(token)).status_code == 403
    res = client.post(f"/api/v1/admin/users/{rising.id}/roles", json={"role": "ADMIN"}, headers=_bearer(admin_token))
    assert res.status_code == 200
    # The pre-promotion session stays PLAYER-active (a granted role never
    # upgrades a live session); a fresh ADMIN-active session gains access.
    assert client.get("/api/v1/admin/dashboard", headers=_bearer(token)).status_code == 403
    admin_session = client.post(
        "/api/v1/auth/login",
        json={"username": "rising", "password": "secret123", "role": "ADMIN"},
    )
    assert admin_session.status_code == 200
    assert client.get(
        "/api/v1/admin/dashboard", headers=_bearer(admin_session.json()["access_token"])
    ).status_code == 200


def test_player_cannot_assign_roles(client, db_session):
    _admin_token(client, db_session)
    player = _register(client, username="sneaky_two").json()["access_token"]
    victim = db_session.query(User).filter(User.username == "sneaky_two").one()
    res = client.post(f"/api/v1/admin/users/{victim.id}/roles", json={"role": "ADMIN"}, headers=_bearer(player))
    assert res.status_code == 403
    db_session.refresh(victim)
    assert [r.role for r in victim.roles] == ["PLAYER"]


# --- exercises ------------------------------------------------------------------


def test_admin_exercise_list_detail_and_validation(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    second = Exercise(slug="ghost_ex", title_fa="روح", is_active=False, sort_order=99)
    db_session.add(second)
    db_session.commit()
    headers = _bearer(admin)

    listing = client.get("/api/v1/admin/exercises", headers=headers)
    assert listing.status_code == 200
    assert {e["slug"] for e in listing.json()} >= {"pin", "ghost_ex"}

    detail = client.get("/api/v1/admin/exercises/pin", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["slug"] == "pin"
    assert "attempts_count" in detail.json()
    assert client.get("/api/v1/admin/exercises/nope", headers=headers).status_code == 404

    updated = client.patch("/api/v1/admin/exercises/pin", json={"title_fa": "آچمز تازه"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["title_fa"] == "آچمز تازه"
    assert client.patch("/api/v1/admin/exercises/pin", json={"title_fa": "  "}, headers=headers).status_code == 422
    assert client.patch("/api/v1/admin/exercises/pin", json={}, headers=headers).status_code == 422


def test_exercise_disable_blocks_new_attempts_but_preserves_history(client, db_session):
    admin = _admin_token(client, db_session)
    puzzle = _seed_puzzle(db_session, slug="pin")
    player_token = _register(client, username="trainee").json()["access_token"]
    headers = _bearer(admin)

    # Baseline: attempt works while enabled.
    ok = client.post("/api/v1/attempts", json={
        "puzzle_id": puzzle.id,
        "answer": {"moves": ["e2e4"]},
        "mode": "practice",
    }, headers=_bearer(player_token))
    assert ok.status_code == 200

    disabled = client.patch("/api/v1/admin/exercises/pin", json={"is_active": False}, headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    # Player catalog hides it; new attempts are refused server-side.
    catalog = client.get("/api/v1/exercises", headers=_bearer(player_token))
    assert "pin" not in [e["slug"] for e in catalog.json()]
    blocked = client.post("/api/v1/attempts", json={
        "puzzle_id": puzzle.id,
        "answer": {"moves": ["e2e4"]},
        "mode": "practice",
    }, headers=_bearer(player_token))
    assert blocked.status_code == 404
    assert blocked.json()["error"]["code"] == "EXERCISE_NOT_AVAILABLE"

    # History remains readable.
    history = client.get("/api/v1/me/training/attempts", headers=_bearer(player_token))
    assert history.status_code == 200
    assert len(history.json()) == 1

    # Re-enable restores new attempts.
    enabled = client.patch("/api/v1/admin/exercises/pin", json={"is_active": True}, headers=headers)
    assert enabled.json()["is_active"] is True
    retry = client.post("/api/v1/attempts", json={
        "puzzle_id": puzzle.id,
        "answer": {"moves": ["e2e4"]},
        "mode": "practice",
    }, headers=_bearer(player_token))
    assert retry.status_code == 200


def test_exercise_enable_requires_implementation(client, db_session):
    admin = _admin_token(client, db_session)
    db_session.add(Exercise(slug="vaporware", title_fa="ناموجود", is_active=False))
    db_session.commit()
    res = client.patch("/api/v1/admin/exercises/vaporware", json={"is_active": True}, headers=_bearer(admin))
    assert res.status_code == 409


def test_player_cannot_change_exercises(client, db_session):
    _seed_exercise(db_session, "pin")
    player = _register(client, username="plain_two").json()["access_token"]
    res = client.patch("/api/v1/admin/exercises/pin", json={"is_active": False}, headers=_bearer(player))
    assert res.status_code == 403
    assert db_session.get(Exercise, "pin").is_active is True


# --- puzzles --------------------------------------------------------------------


def test_admin_puzzle_lifecycle(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)

    # Unknown exercise rejected.
    bad = client.post("/api/v1/admin/puzzles", json={"exercise_slug": "nope", "answer_json": {"a": 1}}, headers=headers)
    assert bad.status_code == 422

    # Draft is invisible to players but fully visible to admins.
    draft = client.post("/api/v1/admin/puzzles", json={
        "exercise_slug": "pin", "answer_json": {"moves": ["e2e4"]}, "prompt_fa": "سوال",
    }, headers=headers)
    assert draft.status_code == 201
    pid = draft.json()["id"]
    assert draft.json()["status"] == "draft"
    assert draft.json()["answer_json"] == {"moves": ["e2e4"]}

    player_token = _register(client, username="learner").json()["access_token"]
    assert client.get(f"/api/v1/puzzles/{pid}", headers=_bearer(player_token)).status_code == 404

    # Draft answer editable.
    upd = client.patch(f"/api/v1/admin/puzzles/{pid}", json={"answer_json": {"moves": ["d2d4"]}}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()["answer_json"] == {"moves": ["d2d4"]}

    # Phase 07 lifecycle: publishing requires validation, review, and
    # approval. Direct publish from draft is rejected server-side.
    assert client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers).status_code == 409

    validated = client.post(f"/api/v1/admin/puzzles/{pid}/validate", headers=headers)
    assert validated.status_code == 200
    assert validated.json()["status"] == "validated"

    # Meaning locks once validated: corrections need request_changes.
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"answer_json": {"moves": ["x"]}}, headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers).status_code == 409

    reviewed = client.post(f"/api/v1/admin/puzzles/{pid}/review", json={"decision": "approve"}, headers=headers)
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    approved = client.post(f"/api/v1/admin/puzzles/{pid}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # Lifecycle trail is inspectable by admins.
    history = client.get(f"/api/v1/admin/puzzles/{pid}/history", headers=headers)
    assert history.status_code == 200
    assert [t["to_status"] for t in history.json()["transitions"]] == ["validated", "reviewed", "approved"]
    assert history.json()["validations"][0]["status"] == "pass"
    assert history.json()["reviews"][0]["decision"] == "approve"

    # Publish makes it player-visible (answer still hidden).
    pub = client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers)
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    visible = client.get(f"/api/v1/puzzles/{pid}", headers=_bearer(player_token))
    assert visible.status_code == 200
    assert "answer_json" not in visible.json()
    # Republishing is idempotent.
    assert client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers).status_code == 200

    # Published content is immutable in meaning.
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"answer_json": {"moves": ["x"]}}, headers=headers).status_code == 409
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"exercise_slug": "pin"}, headers=headers).status_code == 200
    assert client.patch(f"/api/v1/admin/puzzles/{pid}", json={"prompt_fa": "سوال تازه"}, headers=headers).status_code == 200

    # Retire hides from players; history preserved.
    client.post("/api/v1/attempts", json={
        "puzzle_id": pid, "answer": {"moves": ["d2d4"]}, "mode": "practice",
    }, headers=_bearer(player_token))
    retired = client.post(f"/api/v1/admin/puzzles/{pid}/retire", headers=headers)
    assert retired.json()["status"] == "retired"
    assert client.get(f"/api/v1/puzzles/{pid}", headers=_bearer(player_token)).status_code == 404
    history = client.get("/api/v1/me/training/attempts", headers=_bearer(player_token))
    assert len(history.json()) == 1
    # Archived puzzles cannot be republished; retire is idempotent.
    assert client.post(f"/api/v1/admin/puzzles/{pid}/publish", headers=headers).status_code == 409
    assert client.post(f"/api/v1/admin/puzzles/{pid}/retire", headers=headers).status_code == 200


def test_publish_requires_answer(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_exercise(db_session, "pin")
    headers = _bearer(admin)
    draft = client.post("/api/v1/admin/puzzles", json={"exercise_slug": "pin", "prompt_fa": "خالی"}, headers=headers)
    assert draft.status_code == 201
    res = client.post(f"/api/v1/admin/puzzles/{draft.json()['id']}/publish", headers=headers)
    assert res.status_code == 409


def test_admin_puzzle_filters_and_unknown(client, db_session):
    admin = _admin_token(client, db_session)
    _seed_puzzle(db_session, slug="pin", published=True)
    _seed_puzzle(db_session, slug="pin", published=False)
    headers = _bearer(admin)
    drafts = client.get("/api/v1/admin/puzzles?status=draft", headers=headers)
    assert drafts.status_code == 200
    assert all(p["status"] == "draft" for p in drafts.json())
    assert len(drafts.json()) >= 1
    assert client.get("/api/v1/admin/puzzles?status=bogus", headers=headers).status_code == 422
    assert client.get("/api/v1/admin/puzzles/999999", headers=headers).status_code == 404
    assert client.patch("/api/v1/admin/puzzles/999999", json={"prompt_fa": "x"}, headers=headers).status_code == 404


def test_anonymous_puzzle_admin_is_401(client):
    assert client.post("/api/v1/admin/puzzles/1/publish").status_code == 401
    assert client.post("/api/v1/admin/puzzles/1/retire").status_code == 401


# --- audit -----------------------------------------------------------------------


def test_privileged_actions_are_audited_without_secrets(client, db_session):
    admin_token = _admin_token(client, db_session)
    _register(client, username="audited_one")
    target = db_session.query(User).filter(User.username == "audited_one").one()
    headers = _bearer(admin_token)
    client.post(f"/api/v1/admin/users/{target.id}/suspend", headers=headers)
    client.post(f"/api/v1/admin/users/{target.id}/roles", json={"role": "COACH"}, headers=headers)

    rows = db_session.query(AuditLog).order_by(AuditLog.id).all()
    assert len(rows) == 2
    for row in rows:
        assert row.actor_user_id is not None
        assert row.created_at is not None
        assert "password" not in str(row.metadata_json).lower()
        assert "token" not in str(row.metadata_json).lower()

    listing = client.get("/api/v1/admin/audit", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 2
    detail = client.get(f"/api/v1/admin/audit/{rows[0].id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["action"] == "users.suspend"
    assert client.get("/api/v1/admin/audit/999999", headers=headers).status_code == 404


def test_ordinary_requests_create_no_audit(client, db_session):
    player = _register(client, username="quiet_one").json()["access_token"]
    client.get("/api/v1/users/me", headers=_bearer(player))
    client.get("/api/v1/me/dashboard", headers=_bearer(player))
    assert db_session.query(AuditLog).count() == 0


def test_audit_is_read_only(client, db_session):
    admin = _admin_token(client, db_session)
    assert client.put("/api/v1/admin/audit/1", headers=_bearer(admin)).status_code == 405
    assert client.delete("/api/v1/admin/audit/1", headers=_bearer(admin)).status_code == 405


def test_player_cannot_read_audit(client, db_session):
    _admin_token(client, db_session)
    player = _register(client, username="curious").json()["access_token"]
    assert client.get("/api/v1/admin/audit", headers=_bearer(player)).status_code == 403


# --- migration --------------------------------------------------------------------


def test_fresh_database_boots_to_v9_with_content_tables():
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version

    assert SCHEMA_VERSION == 17
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert ensure_schema(engine) == SCHEMA_VERSION
    assert get_schema_version(engine) == SCHEMA_VERSION
    assert "audit_logs" in inspect(engine).get_table_names()
    assert "audit_logs" in Base.metadata.tables
    assert "generator_runs" in inspect(engine).get_table_names()
    assert "puzzle_status_history" in inspect(engine).get_table_names()
    assert "puzzle_validations" in inspect(engine).get_table_names()
    assert "puzzle_reviews" in inspect(engine).get_table_names()
    # Idempotent re-run.
    assert ensure_schema(engine) == SCHEMA_VERSION
    assert "relationships" in inspect(engine).get_table_names()
    assert "assignments" in inspect(engine).get_table_names()
    assert "adaptive_recommendations" in inspect(engine).get_table_names()
    assert "adaptive_recommendations" in Base.metadata.tables
