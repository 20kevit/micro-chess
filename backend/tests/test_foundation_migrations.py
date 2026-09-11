"""Foundation: migration strategy and bounded list endpoints."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.migration import (
    SCHEMA_VERSION,
    ensure_schema,
    get_schema_version,
    import_models,
)


def _fresh_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_import_models_covers_all_exercise_tables():
    imported = import_models()
    assert "app.modules.users.models" in imported
    assert "app.modules.captures.models" in imported
    assert "app.modules.trapped_pieces.models" in imported
    assert "app.modules.gamification_engine.models" in imported
    for table in (
        "users",
        "user_roles",
        "auth_sessions",
        "guest_sessions",
        "player_profiles",
        "player_external_identities",
        "player_ratings",
        "rating_events",
        "player_gamification_state",
        "xp_events",
        "player_streaks",
        "player_achievements",
        "exercises",
        "puzzles",
        "attempts",
        "schema_version",
    ):
        assert table in Base.metadata.tables


def test_fresh_database_boots_to_current_version():
    engine = _fresh_engine()
    version = ensure_schema(engine)
    assert version == SCHEMA_VERSION
    assert get_schema_version(engine) == SCHEMA_VERSION


def test_ensure_schema_is_idempotent_and_preserves_data():
    from app.modules.users.models import User

    engine = _fresh_engine()
    ensure_schema(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(email="keep@example.com", password_hash="x", display_name="Keep"))
    session.commit()
    session.close()

    assert ensure_schema(engine) == SCHEMA_VERSION
    session = sessionmaker(bind=engine)()
    assert session.query(User).filter(User.email == "keep@example.com").count() == 1
    session.close()


def test_existing_database_without_version_row_gets_stamped():
    engine = _fresh_engine()
    import_models()
    Base.metadata.create_all(bind=engine)
    assert get_schema_version(engine) is None
    assert ensure_schema(engine) == SCHEMA_VERSION


def test_newer_database_refuses_to_boot():
    from app.db.migration import _stamp

    engine = _fresh_engine()
    ensure_schema(engine)
    _stamp(engine, SCHEMA_VERSION + 1)
    with pytest.raises(RuntimeError, match="newer than supported"):
        ensure_schema(engine)


def test_puzzle_list_is_bounded(client, db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG

    seed_mod.seed_db(db_session)
    page1 = client.get(f"/api/v1/puzzles?exercise={SLUG}&page=1&page_size=5")
    assert page1.status_code == 200
    assert len(page1.json()) == 5
    page4 = client.get(f"/api/v1/puzzles?exercise={SLUG}&page=4&page_size=5")
    assert page4.status_code == 200
    assert len(page4.json()) == 0
    too_big = client.get(f"/api/v1/puzzles?exercise={SLUG}&page_size=1000")
    assert too_big.status_code == 422
    assert too_big.json()["error"]["code"] == "VALIDATION_ERROR"
