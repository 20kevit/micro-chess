"""Phase 12 admin bootstrap: first-admin promotion via the operations CLI."""

import pytest

from app.cli import main, promote_to_admin
from app.modules.users.models import User, UserRole


def _account(db_session, username, roles=("PLAYER",)):
    user = User(username=username, password_hash="h", display_name=username)
    db_session.add(user)
    db_session.flush()
    for role in roles:
        db_session.add(UserRole(user_id=user.id, role=role))
    db_session.commit()
    db_session.refresh(user)
    return user


def _roles(db_session, username):
    user = db_session.query(User).filter(User.username == username).one()
    return sorted(r.role for r in user.roles)


def test_missing_user_raises_and_creates_nothing(client, db_session):
    with pytest.raises(ValueError, match="user_not_found"):
        promote_to_admin(db_session, "ghost_account")
    assert db_session.query(User).count() == 0


def test_success_promotes_existing_user(db_session):
    _account(db_session, "first_admin")
    assert promote_to_admin(db_session, "first_admin") == "created"
    assert _roles(db_session, "first_admin") == ["ADMIN", "PLAYER"]


def test_username_is_canonicalized(db_session):
    _account(db_session, "boss")
    assert promote_to_admin(db_session, "  BOSS ") == "created"
    assert _roles(db_session, "boss") == ["ADMIN", "PLAYER"]


def test_idempotent_second_call_changes_nothing(db_session):
    _account(db_session, "steady_admin")
    assert promote_to_admin(db_session, "steady_admin") == "created"
    assert promote_to_admin(db_session, "steady_admin") == "already_admin"
    rows = (
        db_session.query(UserRole)
        .join(User, User.id == UserRole.user_id)
        .filter(User.username == "steady_admin", UserRole.role == "ADMIN")
        .all()
    )
    assert len(rows) == 1


def test_only_admin_is_granted(db_session):
    _account(db_session, "plain_boss", roles=("PLAYER", "COACH"))
    promote_to_admin(db_session, "plain_boss")
    assert _roles(db_session, "plain_boss") == ["ADMIN", "COACH", "PLAYER"]


def test_production_requires_explicit_confirmation(db_session):
    _account(db_session, "prod_boss")
    with pytest.raises(RuntimeError, match="production_confirmation_required"):
        promote_to_admin(db_session, "prod_boss", environment="production")
    assert _roles(db_session, "prod_boss") == ["PLAYER"]
    assert (
        promote_to_admin(db_session, "prod_boss", environment="production", allow_production=True)
        == "created"
    )
    assert _roles(db_session, "prod_boss") == ["ADMIN", "PLAYER"]


def test_main_success_and_missing_user_exit_codes(db_session, monkeypatch, capsys):
    import app.db.session as session_mod

    _account(db_session, "cli_admin")
    monkeypatch.setattr(session_mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(session_mod, "init_db", lambda: None)

    assert main(["create-admin", "cli_admin"]) == 0
    assert _roles(db_session, "cli_admin") == ["ADMIN", "PLAYER"]
    out = capsys.readouterr().out
    assert "cli_admin" in out and "ADMIN" in out

    assert main(["create-admin", "cli_admin"]) == 0  # idempotent
    assert "already" in capsys.readouterr().out

    assert main(["create-admin", "ghost_account"]) == 1
    assert "user_not_found" in capsys.readouterr().err


def test_main_refuses_production_without_flag(db_session, monkeypatch):
    import app.db.session as session_mod
    from app.core.config import settings

    _account(db_session, "cli_prod")
    monkeypatch.setattr(session_mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(session_mod, "init_db", lambda: None)
    monkeypatch.setattr(settings, "environment", "production")

    assert main(["create-admin", "cli_prod"]) == 2
    assert _roles(db_session, "cli_prod") == ["PLAYER"]
    assert main(["create-admin", "cli_prod", "--confirm-production"]) == 0
    assert _roles(db_session, "cli_prod") == ["ADMIN", "PLAYER"]
