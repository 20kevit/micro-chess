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
        "audit_logs",
        "generator_runs",
        "puzzle_status_history",
        "puzzle_validations",
        "puzzle_reviews",
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
    from tests.conftest import publish_staged_puzzles

    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    page1 = client.get(f"/api/v1/puzzles?exercise={SLUG}&page=1&page_size=5")
    assert page1.status_code == 200
    assert len(page1.json()) == 5
    page4 = client.get(f"/api/v1/puzzles?exercise={SLUG}&page=4&page_size=5")
    assert page4.status_code == 200
    assert len(page4.json()) == 0
    too_big = client.get(f"/api/v1/puzzles?exercise={SLUG}&page_size=1000")
    assert too_big.status_code == 422
    assert too_big.json()["error"]["code"] == "VALIDATION_ERROR"


def test_v6_database_upgrades_to_v7_with_lifecycle_backfill():
    """A pre-Phase-07 database (legacy puzzles table without lifecycle
    columns) upgrades to v7: status/source/hash backfilled from legacy
    flags, existing rows intact, and the step is safe to re-run."""
    import json

    from sqlalchemy import text

    from app.db.migration import _migrate_v7_content, import_models

    engine = _fresh_engine()
    import_models()
    # Build a legacy-shaped puzzles table (Phase 06 columns only).
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE puzzles ("
                "id INTEGER PRIMARY KEY, exercise_slug VARCHAR(100), fen VARCHAR(255), "
                "position_json JSON, answer_json JSON, hint_json JSON, "
                "prompt_fa VARCHAR(500) DEFAULT '', explanation VARCHAR(2000) DEFAULT '', "
                "initial_rating FLOAT DEFAULT 1200.0, "
                "is_published BOOLEAN DEFAULT 0, is_archived BOOLEAN DEFAULT 0, "
                "published_at DATETIME, created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO puzzles (id, exercise_slug, answer_json, is_published, is_archived) "
                "VALUES (1, 'pin', :a, 0, 0), (2, 'pin', :a, 1, 0), (3, 'pin', :a, 1, 1)"
            ),
            {"a": json.dumps({"moves": ["e2e4"]})},
        )
    with engine.begin() as conn:
        _migrate_v7_content(conn)
    with engine.connect() as conn:
        rows = {
            r[0]: r
            for r in conn.execute(
                text("SELECT id, status, source, content_hash FROM puzzles ORDER BY id")
            ).fetchall()
        }
    assert rows[1][1] == "draft"
    assert rows[2][1] == "published"
    assert rows[3][1] == "retired"
    assert all(r[2] == "manual" for r in rows.values())
    assert all(r[3] for r in rows.values())
    # Re-running never demotes content that already advanced: a puzzle
    # moved to validated keeps its state and hash.
    with engine.begin() as conn:
        conn.execute(text("UPDATE puzzles SET status = 'validated' WHERE id = 1"))
        _migrate_v7_content(conn)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM puzzles WHERE id = 1")).scalar() == "validated"
