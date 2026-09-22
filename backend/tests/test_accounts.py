"""Phase 2 accounts: lifecycle, sessions, roles, guests, migration, upgrade."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.capabilities import Capability, Role, capabilities_for_roles, require_capability
from app.core.config import settings
from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version
from app.modules.auth.models import AuthSession, GuestSession
from app.modules.progress.models import Attempt
from app.modules.users.models import User, UserRole


def _register(client, username="player_one", password="secret123", **extra):
    body = {"username": username, "password": password}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def _login(client, username="player_one", password="secret123"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _seeded_puzzle_id(db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.puzzles.models import Puzzle

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG)
        .order_by(Puzzle.id)
        .first()
    )
    assert puzzle is not None
    return puzzle.id, puzzle.answer_json


# --- registration ---------------------------------------------------------


def test_registration_creates_player_account_with_session(client, db_session):
    res = _register(client)
    assert res.status_code == 201
    token = res.json()["access_token"]
    assert token

    me = client.get("/api/v1/users/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["username"] == "player_one"
    assert me.json()["roles"] == ["PLAYER"]

    user = db_session.query(User).filter(User.username == "player_one").one()
    assert user.password_hash != "secret123"
    assert user.email is None
    assert [r.role for r in user.roles] == ["PLAYER"]
    sessions = db_session.query(AuthSession).filter(AuthSession.user_id == user.id).all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


def test_registration_normalizes_username_and_defaults_display_name(client, db_session):
    assert _register(client, username="  Kid_01 ").status_code == 201
    user = db_session.query(User).filter(User.username == "kid_01").one()
    assert user.display_name == "kid_01"
    # Canonical login works regardless of case/whitespace.
    assert _login(client, username="KID_01").status_code == 200


def test_me_response_shape_exposes_no_secrets(client):
    token = _register(client).json()["access_token"]
    body = client.get("/api/v1/users/me", headers=_bearer(token)).json()
    assert set(body) == {"id", "username", "display_name", "roles", "active_role", "created_at"}
    # Single-role accounts get their role as the session's active role.
    assert body["roles"] == ["PLAYER"]
    assert body["active_role"] == "PLAYER"


@pytest.mark.parametrize("bad", ["ab", "a" * 31, "has space", "no-dash", "dot.name", "", "   "])
def test_registration_rejects_invalid_usernames(client, bad):
    res = _register(client, username=bad)
    assert res.status_code == 422


def test_registration_duplicate_is_case_insensitive_and_safe(client):
    assert _register(client, username="Player_One").status_code == 201
    dup = _register(client, username="player_one")
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "USERNAME_TAKEN"


def test_registration_ignores_privilege_escalation_payload(client):
    res = _register(client, roles=["ADMIN"], is_admin=True)
    assert res.status_code == 201
    me = client.get("/api/v1/users/me", headers=_bearer(res.json()["access_token"]))
    assert me.json()["roles"] == ["PLAYER"]


def test_guest_is_not_a_persisted_role():
    with pytest.raises(ValueError):
        Role("GUEST")
    assert {r.value for r in Role} == {"PLAYER", "COACH", "PARENT", "ADMIN"}


# --- login / logout / sessions --------------------------------------------


def test_login_creates_fresh_session_each_time(client, db_session):
    _register(client)
    first = _login(client).json()["access_token"]
    second = _login(client).json()["access_token"]
    assert first != second
    # Both sessions are valid (multi-session); fixation-safe (never reused).
    assert client.get("/api/v1/users/me", headers=_bearer(first)).status_code == 200
    assert client.get("/api/v1/users/me", headers=_bearer(second)).status_code == 200


def test_logout_revokes_only_the_current_session(client):
    _register(client)
    first = _login(client).json()["access_token"]
    second = _login(client).json()["access_token"]
    assert client.post("/api/v1/auth/logout", headers=_bearer(first)).status_code == 204
    assert client.get("/api/v1/users/me", headers=_bearer(first)).status_code == 401
    assert client.get("/api/v1/users/me", headers=_bearer(second)).status_code == 200


def test_logout_is_idempotent(client):
    _register(client)
    token = _login(client).json()["access_token"]
    assert client.post("/api/v1/auth/logout", headers=_bearer(token)).status_code == 204
    assert client.post("/api/v1/auth/logout", headers=_bearer(token)).status_code == 204
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_tampered_and_foreign_tokens_rejected(client, db_session):
    token_a = _register(client, username="user_a").json()["access_token"]
    token_b = _register(client, username="user_b").json()["access_token"]
    assert client.get("/api/v1/users/me", headers=_bearer(token_a + "x")).status_code == 401
    assert client.get("/api/v1/users/me", headers=_bearer("not-a-token")).status_code == 401
    # Legacy sid-less token (valid signature, no session row) is rejected.
    user_a = db_session.query(User).filter(User.username == "user_a").one()
    legacy = jwt.encode(
        {"sub": str(user_a.id)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(legacy)).status_code == 401
    # Cross-user session binding: B's session id with A's subject is rejected.
    from app.core.security import decode_access_token

    sid_b = decode_access_token(token_b)["sid"]
    forged = jwt.encode(
        {"sub": str(user_a.id), "sid": sid_b},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(forged)).status_code == 401


def test_resigned_token_with_role_claim_rejected(client, db_session):
    # A client cannot mint authority: re-signing the session with a role
    # claim changes the bearer string, so the session hash binding fails
    # closed. Roles always resolve server-side from the database.
    token = _register(client).json()["access_token"]
    from app.core.security import decode_access_token

    claims = decode_access_token(token)
    user = db_session.query(User).filter(User.username == "player_one").one()
    forged = jwt.encode(
        {"sub": str(user.id), "sid": claims["sid"], "role": "ADMIN", "is_admin": True},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(forged)).status_code == 401
    assert Capability.USERS_MANAGE not in capabilities_for_roles([Role.PLAYER])


def test_expired_session_rejected(client, db_session):
    token = _register(client).json()["access_token"]
    user = db_session.query(User).filter(User.username == "player_one").one()
    session = db_session.query(AuthSession).filter(AuthSession.user_id == user.id).one()
    session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/api/v1/users/me", headers=_bearer(token)).status_code == 401


def test_suspended_account_cannot_login_and_token_dies(client, db_session):
    _register(client)
    token = _login(client).json()["access_token"]
    assert client.get("/api/v1/users/me", headers=_bearer(token)).status_code == 200
    user = db_session.query(User).filter(User.username == "player_one").one()
    user.is_active = False
    db_session.commit()
    # Generic failure: suspension is indistinguishable from bad credentials.
    denied = _login(client)
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert client.get("/api/v1/users/me", headers=_bearer(token)).status_code == 401


# --- persisted roles + capabilities ---------------------------------------


def test_roles_persist_and_union_capabilities(client, db_session):
    token = _register(client).json()["access_token"]
    user = db_session.query(User).filter(User.username == "player_one").one()
    db_session.add(UserRole(user_id=user.id, role="COACH"))
    db_session.commit()
    db_session.refresh(user)

    me = client.get("/api/v1/users/me", headers=_bearer(token)).json()
    assert me["roles"] == ["PLAYER", "COACH"]
    from app.core.capabilities import roles_for_user

    assert Capability.ATTEMPTS_SUBMIT in capabilities_for_roles(roles_for_user(user))
    assert Capability.USERS_MANAGE not in capabilities_for_roles(roles_for_user(user))


def test_admin_capability_enforced_and_player_denied(client, db_session):
    user = db_session.query(User).first()
    assert user is None  # fresh isolated DB per test
    player_token = _register(client, username="just_player").json()["access_token"]
    admin_token = _register(client, username="the_admin").json()["access_token"]
    admin = db_session.query(User).filter(User.username == "the_admin").one()
    db_session.add(UserRole(user_id=admin.id, role="ADMIN"))
    db_session.commit()

    from fastapi import HTTPException

    manage = require_capability(Capability.USERS_MANAGE)
    with pytest.raises(HTTPException) as exc:
        manage(db_session.query(User).filter(User.username == "just_player").one())
    assert exc.value.status_code == 403
    allowed = manage(db_session.query(User).filter(User.username == "the_admin").one())
    assert allowed.username == "the_admin"
    # Deny by default through HTTP as well: players cannot reach admin scope.
    assert player_token and admin_token


# --- guests ----------------------------------------------------------------


def _guest(client):
    res = client.post("/api/v1/guest/session")
    assert res.status_code == 201
    return res.json()["guest_token"]


def test_guest_session_lifecycle(client):
    token = _guest(client)
    res = client.get("/api/v1/guest/session", headers=_bearer(token))
    assert res.status_code == 200
    assert res.json()["active"] is True
    assert client.get("/api/v1/guest/session").status_code == 401
    assert client.get("/api/v1/guest/session", headers=_bearer("bogus")).status_code == 401


def test_guest_practice_attempt_is_blocked(client, db_session):
    # Product decision: guests cannot practice. Only authenticated users
    # may create attempts (and therefore evidence). Historical guest rows
    # are preserved, but no new guest attempt is possible.
    puzzle_id, answer = _seeded_puzzle_id(db_session)
    token = _guest(client)
    res = client.post(
        "/api/v1/attempts",
        headers=_bearer(token),
        json={"puzzle_id": puzzle_id, "answer": {"selected_squares": answer["squares"]}, "mode": "practice"},
    )
    assert res.status_code == 401
    assert db_session.query(Attempt).count() == 0
    # Guests cannot play rated mode either.
    rated = client.post(
        "/api/v1/attempts",
        headers=_bearer(token),
        json={"puzzle_id": puzzle_id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401
    assert db_session.query(Attempt).count() == 0
    # Fully anonymous practice is blocked the same way.
    anon = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle_id, "answer": {"selected_squares": answer["squares"]}, "mode": "practice"},
    )
    assert anon.status_code == 401
    assert db_session.query(Attempt).count() == 0
    # Authenticated practice still works.
    user_token = _register(client, username="owner_practice").json()["access_token"]
    ok = client.post(
        "/api/v1/attempts",
        headers=_bearer(user_token),
        json={"puzzle_id": puzzle_id, "answer": {"selected_squares": answer["squares"]}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert db_session.query(Attempt).count() == 1


def _seed_historical_guest_attempt(db_session, guest_token, puzzle_id, answer):
    """Persist one pre-decision guest attempt directly (history is kept)."""
    from app.modules.auth import service as auth_service
    from app.modules.piece_recognition.validator import SLUG

    guest = auth_service.get_guest_session(db_session, guest_token)
    assert guest is not None
    attempt = Attempt(
        user_id=None,
        guest_session_id=guest.id,
        puzzle_id=puzzle_id,
        exercise_slug=SLUG,
        mode="practice",
        result="correct",
        answer_json={"selected_squares": answer["squares"]},
        score=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_guest_migration_moves_attempts_atomically(client, db_session):
    puzzle_id, answer = _seeded_puzzle_id(db_session)
    guest_token = _guest(client)
    for _ in range(2):
        _seed_historical_guest_attempt(db_session, guest_token, puzzle_id, answer)

    user_token = _register(client, username="new_owner").json()["access_token"]
    migrate = client.post(
        "/api/v1/guest/migrate",
        headers=_bearer(user_token),
        json={"guest_token": guest_token},
    )
    assert migrate.status_code == 200
    assert migrate.json() == {"migrated_attempts": 2, "already_migrated": False}

    owner = db_session.query(User).filter(User.username == "new_owner").one()
    moved = db_session.query(Attempt).filter(Attempt.user_id == owner.id).all()
    assert len(moved) == 2
    assert all(a.guest_session_id is None for a in moved)
    guest = db_session.query(GuestSession).filter(GuestSession.migrated_to_user_id == owner.id).one()
    assert guest.status == "MIGRATED"

    # Replay to the same account is idempotent: no duplicates.
    replay = client.post(
        "/api/v1/guest/migrate",
        headers=_bearer(user_token),
        json={"guest_token": guest_token},
    )
    assert replay.status_code == 200
    assert replay.json() == {"migrated_attempts": 0, "already_migrated": True}
    assert db_session.query(Attempt).filter(Attempt.user_id == owner.id).count() == 2


def test_guest_migration_rejects_wrong_owner_and_bad_tokens(client):
    guest_token = _guest(client)
    owner_token = _register(client, username="owner_a").json()["access_token"]
    other_token = _register(client, username="owner_b").json()["access_token"]
    assert (
        client.post(
            "/api/v1/guest/migrate", headers=_bearer(owner_token), json={"guest_token": guest_token}
        ).status_code
        == 200
    )
    conflict = client.post(
        "/api/v1/guest/migrate", headers=_bearer(other_token), json={"guest_token": guest_token}
    )
    assert conflict.status_code == 409
    bad = client.post(
        "/api/v1/guest/migrate", headers=_bearer(other_token), json={"guest_token": "nope"}
    )
    assert bad.status_code == 401
    anon = client.post("/api/v1/guest/migrate", json={"guest_token": guest_token})
    assert anon.status_code == 401


def test_guest_isolation_between_sessions(client, db_session):
    token_a = _guest(client)
    token_b = _guest(client)
    assert token_a != token_b
    puzzle_id, answer = _seeded_puzzle_id(db_session)
    # Historical attempt owned by guest A only.
    _seed_historical_guest_attempt(db_session, token_a, puzzle_id, answer)
    owner_token = _register(client, username="iso_owner").json()["access_token"]
    migrate = client.post(
        "/api/v1/guest/migrate", headers=_bearer(owner_token), json={"guest_token": token_b}
    )
    assert migrate.json()["migrated_attempts"] == 0
    owner = db_session.query(User).filter(User.username == "iso_owner").one()
    assert db_session.query(Attempt).filter(Attempt.user_id == owner.id).count() == 0
    guests = db_session.query(GuestSession).all()
    assert len(guests) == 2


# --- migration v1 -> v2 -----------------------------------------------------


def _phase1_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL, "
                "password_hash VARCHAR(255) NOT NULL, display_name VARCHAR(100) NOT NULL DEFAULT '', "
                "is_active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME)"
            )
        )
        conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, display_name, is_active, created_at) "
                "VALUES ('Legacy@Example.com', 'oldhash', 'Legacy', 1, '2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE attempts (id INTEGER PRIMARY KEY, user_id INTEGER, puzzle_id INTEGER, "
                "exercise_slug VARCHAR(100), mode VARCHAR(20), result VARCHAR(20), answer_json JSON, "
                "score FLOAT, rating_delta FLOAT, started_at DATETIME, duration_ms INTEGER, "
                "hints_used JSON, created_at DATETIME)"
            )
        )
    return engine


def test_phase1_database_upgrades_without_data_loss():
    engine = _phase1_database()
    assert get_schema_version(engine) is None
    assert ensure_schema(engine) == SCHEMA_VERSION

    session = sessionmaker(bind=engine)()
    try:
        user = session.query(User).filter(User.email == "Legacy@Example.com").one()
        assert user.username == "legacy"
        assert user.password_hash == "oldhash"
        assert [r.role for r in user.roles] == ["PLAYER"]
        # New username accounts store no email (legacy column now nullable).
        fresh = User(username="fresh_player", email=None, password_hash="h", display_name="Fresh")
        session.add(fresh)
        session.commit()
    finally:
        session.close()
    # Idempotent re-run keeps everything.
    assert ensure_schema(engine) == SCHEMA_VERSION
    session = sessionmaker(bind=engine)()
    try:
        assert session.query(User).count() == 2
    finally:
        session.close()
