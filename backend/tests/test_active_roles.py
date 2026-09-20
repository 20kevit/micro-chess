"""Phase 12 active roles: session role model, login selection, switching,
active-role authorization, and the v10 -> v11 session migration."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version
from app.modules.users.models import User, UserRole


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _login(client, username, password="secret123", role=None):
    body = {"username": username, "password": password}
    if role is not None:
        body["role"] = role
    return client.post("/api/v1/auth/login", json=body)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _grant(db_session, username, role):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, role)) is None:
        db_session.add(UserRole(user_id=user.id, role=role))
        db_session.commit()
    return user


def _login_role(client, username, role, password="secret123"):
    res = _login(client, username, password=password, role=role)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _me(client, token):
    return client.get("/api/v1/users/me", headers=_bearer(token))


# --- login ------------------------------------------------------------------


def test_single_role_login_is_backward_compatible(client):
    assert _register(client, username="solo").status_code == 201
    res = _login(client, username="solo")
    assert res.status_code == 200
    assert res.json()["access_token"]
    me = _me(client, res.json()["access_token"])
    assert me.status_code == 200
    assert me.json()["roles"] == ["PLAYER"]
    assert me.json()["active_role"] == "PLAYER"


def test_single_role_login_accepts_matching_role(client):
    _register(client, username="solo_match")
    res = _login(client, username="solo_match", role="PLAYER")
    assert res.status_code == 200
    assert _me(client, res.json()["access_token"]).json()["active_role"] == "PLAYER"


def test_single_role_login_rejects_other_role(client):
    _register(client, username="solo_strict")
    res = _login(client, username="solo_strict", role="COACH")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_ROLE"


def test_multi_role_login_requires_selection(client, db_session):
    _register(client, username="multi")
    _grant(db_session, "multi", "COACH")
    res = _login(client, username="multi")
    assert res.status_code == 409
    body = res.json()
    # Exact error envelope: machine code + legacy detail + assigned roles.
    assert body["error"]["code"] == "ROLE_SELECTION_REQUIRED"
    assert body["detail"] == "role_selection_required"
    assert body["error"]["details"] == {"roles": ["PLAYER", "COACH"]}


def test_multi_role_login_with_valid_role(client, db_session):
    _register(client, username="coach_pick")
    _grant(db_session, "coach_pick", "COACH")
    token = _login_role(client, "coach_pick", "COACH")
    me = _me(client, token).json()
    assert me["roles"] == ["PLAYER", "COACH"]
    assert me["active_role"] == "COACH"


def test_login_with_unknown_role_rejected(client, db_session):
    _register(client, username="picky")
    _grant(db_session, "picky", "COACH")
    res = _login(client, username="picky", role="WIZARD")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_ROLE"


def test_login_with_unassigned_role_rejected(client, db_session):
    _register(client, username="no_admin")
    _grant(db_session, "no_admin", "COACH")
    # ADMIN is canonical but not assigned to this user: same generic code,
    # no hint about which roles any account holds.
    res = _login(client, username="no_admin", role="ADMIN")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_ROLE"


def test_bad_credentials_reveal_nothing_about_roles(client, db_session):
    _register(client, username="guarded")
    _grant(db_session, "guarded", "COACH")
    res = _login(client, username="guarded", password="wrong-password", role="ADMIN")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


# --- role switching ----------------------------------------------------------


def test_switch_active_role_changes_only_current_session(client, db_session):
    _register(client, username="switcher")
    _grant(db_session, "switcher", "COACH")
    first = _login_role(client, "switcher", "COACH")
    second = _login_role(client, "switcher", "COACH")

    res = client.post(
        "/api/v1/auth/active-role", json={"role": "PLAYER"}, headers=_bearer(first)
    )
    assert res.status_code == 200
    assert res.json() == {"active_role": "PLAYER", "roles": ["PLAYER", "COACH"]}

    assert _me(client, first).json()["active_role"] == "PLAYER"
    # The other session is untouched.
    assert _me(client, second).json()["active_role"] == "COACH"


def test_switch_to_unassigned_role_rejected_and_session_unchanged(client, db_session):
    _register(client, username="steady")
    _grant(db_session, "steady", "COACH")
    token = _login_role(client, "steady", "COACH")
    res = client.post(
        "/api/v1/auth/active-role", json={"role": "ADMIN"}, headers=_bearer(token)
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_ROLE"
    assert _me(client, token).json()["active_role"] == "COACH"


def test_switch_with_unknown_role_rejected(client):
    token = _register(client, username="plain").json()["access_token"]
    res = client.post(
        "/api/v1/auth/active-role", json={"role": "WIZARD"}, headers=_bearer(token)
    )
    assert res.status_code == 422
    assert _me(client, token).json()["active_role"] == "PLAYER"


def test_switch_requires_authentication(client):
    assert client.post("/api/v1/auth/active-role", json={"role": "PLAYER"}).status_code == 401


def test_switch_does_not_modify_assigned_roles(client, db_session):
    _register(client, username="stable_roles")
    _grant(db_session, "stable_roles", "COACH")
    token = _login_role(client, "stable_roles", "COACH")
    before = _me(client, token).json()["roles"]
    client.post("/api/v1/auth/active-role", json={"role": "PLAYER"}, headers=_bearer(token))
    after = _me(client, token).json()["roles"]
    assert before == after == ["PLAYER", "COACH"]
    user = db_session.query(User).filter(User.username == "stable_roles").one()
    assert sorted(r.role for r in user.roles) == ["COACH", "PLAYER"]


# --- revoked roles fail closed ----------------------------------------------


def test_revoked_active_role_fails_closed_and_relogin_recovers(client, db_session):
    _register(client, username="demoted")
    _grant(db_session, "demoted", "COACH")
    token = _login_role(client, "demoted", "COACH")

    user = db_session.query(User).filter(User.username == "demoted").one()
    row = db_session.get(UserRole, (user.id, "COACH"))
    db_session.delete(row)
    db_session.commit()

    # The session gains no other role automatically: every request fails.
    assert _me(client, token).status_code == 401
    assert client.get("/api/v1/admin/dashboard", headers=_bearer(token)).status_code == 401
    # A fresh login picks the remaining role and works again.
    fresh = _login(client, username="demoted")
    assert fresh.status_code == 200
    assert _me(client, fresh.json()["access_token"]).json()["active_role"] == "PLAYER"


# --- authorization respects the active role ----------------------------------


def test_player_session_of_admin_user_cannot_reach_admin(client, db_session):
    _register(client, username="dual")
    _grant(db_session, "dual", "ADMIN")
    player_session = _login_role(client, "dual", "PLAYER")
    assert client.get("/api/v1/admin/dashboard", headers=_bearer(player_session)).status_code == 403
    assert client.get("/api/v1/admin/users", headers=_bearer(player_session)).status_code == 403

    admin_session = _login_role(client, "dual", "ADMIN")
    assert client.get("/api/v1/admin/dashboard", headers=_bearer(admin_session)).status_code == 200


def test_admin_session_keeps_player_capabilities(client, db_session):
    _register(client, username="boss_player")
    _grant(db_session, "boss_player", "ADMIN")
    token = _login_role(client, "boss_player", "ADMIN")
    me = _me(client, token)
    assert me.status_code == 200
    assert me.json()["active_role"] == "ADMIN"


def _relationship_ids(client, coach_token, student_username):
    created = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": student_username},
        headers=_bearer(coach_token),
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_coach_scope_enforced_under_both_active_roles(client, db_session):
    _register(client, username="coach_dual")
    _grant(db_session, "coach_dual", "COACH")
    _register(client, username="pupil")
    _register(client, username="stranger")
    coach_token = _login_role(client, "coach_dual", "COACH")

    rel_id = _relationship_ids(client, coach_token, "pupil")
    pupil_id = client.get("/api/v1/users/me", headers=_bearer(
        _login(client, username="pupil").json()["access_token"])).json()["id"]
    stranger_id = client.get("/api/v1/users/me", headers=_bearer(
        _login(client, username="stranger").json()["access_token"])).json()["id"]
    # The student accepts the pending invitation.
    accept = client.post(
        f"/api/v1/relationships/{rel_id}/accept",
        headers=_bearer(_login(client, username="pupil").json()["access_token"]),
    )
    assert accept.status_code == 200

    own = f"/api/v1/coach/students/{pupil_id}/progress"
    foreign = f"/api/v1/coach/students/{stranger_id}/progress"
    assert client.get(own, headers=_bearer(coach_token)).status_code == 200
    assert client.get(foreign, headers=_bearer(coach_token)).status_code == 404

    # The same edge under a PLAYER-active session: object-level scope is
    # unchanged (related reads work, foreign ids stay 404).
    client.post("/api/v1/auth/active-role", json={"role": "PLAYER"}, headers=_bearer(coach_token))
    assert client.get(own, headers=_bearer(coach_token)).status_code == 200
    assert client.get(foreign, headers=_bearer(coach_token)).status_code == 404


def test_parent_scope_enforced_with_active_role(client, db_session):
    _register(client, username="parent_dual")
    _grant(db_session, "parent_dual", "PARENT")
    _register(client, username="kiddo")
    parent_token = _login_role(client, "parent_dual", "PARENT")

    created = client.post(
        "/api/v1/relationships",
        json={"kind": "parent", "other_username": "kiddo"},
        headers=_bearer(parent_token),
    )
    assert created.status_code == 201, created.text
    kid_token = _login(client, username="kiddo").json()["access_token"]
    accept = client.post(
        f"/api/v1/relationships/{created.json()['id']}/accept", headers=_bearer(kid_token)
    )
    assert accept.status_code == 200
    kid_id = client.get("/api/v1/users/me", headers=_bearer(kid_token)).json()["id"]

    assert client.get(
        f"/api/v1/parent/children/{kid_id}/progress", headers=_bearer(parent_token)
    ).status_code == 200
    assert client.get(
        "/api/v1/parent/children/999999/progress", headers=_bearer(parent_token)
    ).status_code == 404


# --- v10 -> v11 session migration --------------------------------------------


def _v10_database():
    """Pre-Phase-12 shape: auth_sessions without active_role, stamped v10."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(30), "
                "email VARCHAR(255), password_hash VARCHAR(255) NOT NULL, "
                "display_name VARCHAR(100) NOT NULL DEFAULT '', "
                "is_active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE user_roles (user_id INTEGER NOT NULL, role VARCHAR(20) NOT NULL, "
                "created_at DATETIME, PRIMARY KEY (user_id, role))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE auth_sessions (id INTEGER PRIMARY KEY, "
                "public_id VARCHAR(64) NOT NULL, user_id INTEGER NOT NULL, "
                "token_hash VARCHAR(64) NOT NULL, created_at DATETIME, "
                "expires_at DATETIME, revoked_at DATETIME)"
            )
        )
        conn.execute(text("INSERT INTO users (username, password_hash, display_name) VALUES ('solo_v10', 'h', 'Solo')"))
        conn.execute(text("INSERT INTO users (username, password_hash, display_name) VALUES ('multi_v10', 'h', 'Multi')"))
        conn.execute(text("INSERT INTO user_roles (user_id, role) VALUES (1, 'PLAYER')"))
        conn.execute(text("INSERT INTO user_roles (user_id, role) VALUES (2, 'PLAYER')"))
        conn.execute(text("INSERT INTO user_roles (user_id, role) VALUES (2, 'COACH')"))
        conn.execute(
            text(
                "INSERT INTO auth_sessions (public_id, user_id, token_hash, expires_at) "
                "VALUES ('sid-solo', 1, 'aa', '2030-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO auth_sessions (public_id, user_id, token_hash, expires_at) "
                "VALUES ('sid-multi', 2, 'bb', '2030-01-01 00:00:00')"
            )
        )
        conn.execute(text("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at VARCHAR(32))"))
        conn.execute(text("INSERT INTO schema_version (version, applied_at) VALUES (10, '2026-01-01T00:00:00')"))
    return engine


def test_v10_sessions_upgrade_with_deterministic_active_role():
    engine = _v10_database()
    assert get_schema_version(engine) == 10
    assert ensure_schema(engine) == SCHEMA_VERSION == 15

    session = sessionmaker(bind=engine)()
    try:
        from app.modules.auth.models import AuthSession

        solo = session.query(AuthSession).filter(AuthSession.public_id == "sid-solo").one()
        multi = session.query(AuthSession).filter(AuthSession.public_id == "sid-multi").one()
        # Single-role keeps its role; multi-role defaults to first canonical.
        assert solo.active_role == "PLAYER"
        assert multi.active_role == "PLAYER"
        assert solo.token_hash == "aa"
        assert multi.token_hash == "bb"
    finally:
        session.close()
    # Idempotent re-run preserves chosen roles.
    assert ensure_schema(engine) == SCHEMA_VERSION
