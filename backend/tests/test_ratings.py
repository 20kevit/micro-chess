"""Phase 4 ratings: per-exercise server-authoritative ratings + history.

Covers creation, deterministic updates, provisional state, practice
exclusion, immutable history, idempotency, ownership, multi-exercise
independence, external-rating separation, and the v3 -> v4 migration.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.migration import SCHEMA_VERSION, ensure_schema, import_models
from app.db.base import Base
from app.modules.rating_engine import service as ratings
from app.modules.rating_engine.models import PlayerRating, RatingEvent


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _seeded_piece_puzzle(db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.puzzles.models import Puzzle

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    assert len(puzzle.answer_json.get("squares", [])) >= 2
    return puzzle


def _seeded_legal_puzzle(db_session):
    from app.modules.legal_destinations import seed as seed_mod
    from app.modules.legal_destinations.validator import SLUG
    from app.modules.puzzles.models import Puzzle

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def _submit(client, token, puzzle_id, answer, mode="rated"):
    return client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle_id, "answer": answer, "mode": mode},
        headers=_bearer(token),
    )


def _correct_answer(puzzle):
    return {"selected_squares": list(puzzle.answer_json["squares"])}


def _wrong_answer():
    # Malformed-only selections are never correct (validator contract).
    return {"selected_squares": ["not-a-square"]}


def _partial_answer(puzzle):
    squares = list(puzzle.answer_json["squares"])
    return {"selected_squares": [squares[0], "not-a-square"]}


# --- auth boundaries --------------------------------------------------------


def test_rating_endpoints_require_authentication(client):
    for path in [
        "/api/v1/me/ratings",
        "/api/v1/me/ratings/piece-recognition",
        "/api/v1/me/ratings/piece-recognition/history",
    ]:
        res = client.get(path)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "AUTH_REQUIRED"


# --- creation -----------------------------------------------------------------


def test_first_rated_attempt_creates_rating_at_initial_state(client, db_session):
    token = _token(client, "rater_one")
    puzzle = _seeded_piece_puzzle(db_session)

    assert client.get("/api/v1/me/ratings", headers=_bearer(token)).json() == {"items": []}

    res = _submit(client, token, puzzle.id, _correct_answer(puzzle))
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "correct"
    assert body["rating_before"] == ratings.INITIAL_RATING == 1200.0
    assert body["rating_delta"] is not None
    assert body["rating_after"] == pytest.approx(body["rating_before"] + body["rating_delta"])

    from app.modules.piece_recognition.validator import SLUG

    detail = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token))
    assert detail.status_code == 200
    rating = detail.json()
    assert rating["exercise"] == SLUG
    assert rating["rating"] == body["rating_after"]
    assert rating["rating_deviation"] < ratings.INITIAL_RD
    assert rating["provisional"] is True
    assert rating["attempts_count"] == 1
    assert rating["updated_at"]

    listed = client.get("/api/v1/me/ratings", headers=_bearer(token)).json()
    assert [row["exercise"] for row in listed["items"]] == [SLUG]

    row = db_session.query(PlayerRating).one()
    from app.modules.users.models import User

    owner = db_session.query(User).filter(User.username == "rater_one").one()
    assert row.user_id == owner.id
    assert row.exercise_slug == SLUG


def test_unknown_exercise_404s_and_known_exercise_without_rating_404s(client, db_session):
    token = _token(client, "rater_two")
    _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    missing = client.get("/api/v1/me/ratings/no-such-exercise", headers=_bearer(token))
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "EXERCISE_NOT_FOUND"
    assert (
        client.get("/api/v1/me/ratings/no-such-exercise/history", headers=_bearer(token)).status_code
        == 404
    )

    # Known exercise, but this player has no rated attempts yet.
    norating = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token))
    assert norating.status_code == 404
    assert norating.json()["error"]["code"] == "RATING_NOT_FOUND"
    assert (
        client.get(f"/api/v1/me/ratings/{SLUG}/history", headers=_bearer(token)).json()
        == {"items": []}
    )


# --- deterministic updates ------------------------------------------------------


def test_correct_increases_wrong_decreases_and_chain_is_exact(client, db_session):
    token = _token(client, "rater_chain")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.progress.models import Attempt

    payloads = [_correct_answer(puzzle), _wrong_answer(), _partial_answer(puzzle)]
    for payload in payloads:
        assert _submit(client, token, puzzle.id, payload).status_code == 200

    attempts = db_session.query(Attempt).order_by(Attempt.id).all()
    assert [a.result for a in attempts] == ["correct", "wrong", "partial"]

    expected_rating, expected_rd, games = ratings.INITIAL_RATING, ratings.INITIAL_RD, 0
    for attempt in attempts:
        update = ratings.calculate_update(
            rating_before=expected_rating,
            rd_before=expected_rd,
            games_before=games,
            score=ratings.score_for_result(attempt.result),
            opponent_rating=puzzle.initial_rating,
        )
        assert attempt.rating_before == pytest.approx(update.rating_before)
        assert attempt.rating_delta == pytest.approx(update.rating_delta)
        assert attempt.rating_after == pytest.approx(update.rating_after)
        expected_rating, expected_rd, games = (
            update.rating_after,
            update.rd_after,
            update.games_after,
        )

    assert attempts[0].rating_delta > 0  # correct beats expectation
    assert attempts[1].rating_delta < 0  # wrong loses rating
    from app.modules.piece_recognition.validator import SLUG

    current = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert current["rating"] == pytest.approx(expected_rating)
    assert current["rating_deviation"] == pytest.approx(expected_rd)


def test_provisional_state_flips_after_threshold(client, db_session):
    token = _token(client, "rater_prov")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    for _ in range(ratings.PROVISIONAL_THRESHOLD - 1):
        _submit(client, token, puzzle.id, _correct_answer(puzzle))
    mid = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert mid["attempts_count"] == ratings.PROVISIONAL_THRESHOLD - 1
    assert mid["provisional"] is True

    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    final = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert final["attempts_count"] == ratings.PROVISIONAL_THRESHOLD
    assert final["provisional"] is False


def test_rating_bounds_and_deviation_floor_are_respected():
    # Near the ceiling, an upset win still clamps at the maximum.
    update = ratings.calculate_update(
        rating_before=2995.0, rd_before=60.0, games_before=50,
        score=1.0, opponent_rating=3000.0,
    )
    assert update.rating_after == ratings.RATING_MAX == 3000.0
    assert update.rating_after == pytest.approx(update.rating_before + update.rating_delta)

    # Near the floor, an upset loss still clamps at the minimum.
    update = ratings.calculate_update(
        rating_before=105.0, rd_before=60.0, games_before=50,
        score=0.0, opponent_rating=100.0,
    )
    assert update.rating_after == ratings.RATING_MIN == 100.0
    assert update.rating_after == pytest.approx(update.rating_before + update.rating_delta)

    update = ratings.calculate_update(
        rating_before=1200.0, rd_before=51.0, games_before=200,
        score=1.0, opponent_rating=1200.0,
    )
    assert update.rd_after == ratings.RD_MIN == 50.0


# --- rated vs practice ----------------------------------------------------------


def test_practice_attempt_leaves_rating_untouched(client, db_session):
    token = _token(client, "rater_practice")
    puzzle = _seeded_piece_puzzle(db_session)

    res = _submit(client, token, puzzle.id, _correct_answer(puzzle), mode="practice")
    assert res.json()["result"] == "correct"
    assert res.json()["rating_before"] is None
    assert res.json()["rating_delta"] is None
    assert res.json()["rating_after"] is None

    assert db_session.query(PlayerRating).count() == 0
    assert db_session.query(RatingEvent).count() == 0
    assert client.get("/api/v1/me/ratings", headers=_bearer(token)).json() == {"items": []}


def test_terminal_rated_submission_is_recorded_but_not_rated(client, db_session):
    token = _token(client, "rater_timeout")
    puzzle = _seeded_piece_puzzle(db_session)

    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "rated", "client_result": "timeout"},
        headers=_bearer(token),
    )
    assert res.status_code == 200
    assert res.json()["result"] == "timeout"
    assert res.json()["rating_delta"] is None
    assert db_session.query(PlayerRating).count() == 0
    assert db_session.query(RatingEvent).count() == 0


def test_guest_practice_creates_no_rating(client, db_session):
    puzzle = _seeded_piece_puzzle(db_session)
    guest_token = client.post("/api/v1/guest/session").json()["guest_token"]
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "practice"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert res.status_code == 200
    assert db_session.query(PlayerRating).count() == 0
    assert db_session.query(RatingEvent).count() == 0


# --- history --------------------------------------------------------------------


def test_history_records_full_transition_and_paginates(client, db_session):
    token = _token(client, "rater_hist")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    first = _submit(client, token, puzzle.id, _correct_answer(puzzle)).json()
    second = _submit(client, token, puzzle.id, _wrong_answer()).json()

    history = client.get(f"/api/v1/me/ratings/{SLUG}/history", headers=_bearer(token)).json()
    assert [item["attempt_id"] for item in history["items"]] == [second["id"], first["id"]]
    assert set(history["items"][0]) == {
        "attempt_id", "before", "delta", "after",
        "rating_deviation_before", "rating_deviation_after",
        "reason", "occurred_at",
    }
    newest = history["items"][0]
    assert newest["before"] == first["rating_after"]
    assert newest["rating_deviation_after"] < newest["rating_deviation_before"]

    page1 = client.get(
        f"/api/v1/me/ratings/{SLUG}/history?page=1&page_size=1", headers=_bearer(token)
    ).json()
    assert [item["attempt_id"] for item in page1["items"]] == [second["id"]]
    assert (
        client.get(f"/api/v1/me/ratings/{SLUG}/history?page_size=1000", headers=_bearer(token))
    ).status_code == 422


def test_rating_history_has_no_write_endpoints(client, db_session):
    token = _token(client, "rater_locked")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    headers = _bearer(token)
    # No client-facing mutation endpoint for ratings or their history.
    assert client.post("/api/v1/me/ratings", headers=headers).status_code == 405
    assert client.patch(f"/api/v1/me/ratings/{SLUG}", headers=headers).status_code == 405
    assert client.delete(f"/api/v1/me/ratings/{SLUG}", headers=headers).status_code == 405
    assert (
        client.post(f"/api/v1/me/ratings/{SLUG}/history", headers=headers).status_code == 405
    )


# --- idempotency ------------------------------------------------------------------


def test_reprocessing_same_attempt_does_not_double_update(client, db_session):
    token = _token(client, "rater_idem")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.progress.models import Attempt
    from app.modules.users.models import User

    attempt_id = _submit(client, token, puzzle.id, _correct_answer(puzzle)).json()["id"]
    owner = db_session.query(User).filter(User.username == "rater_idem").one()
    before = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()

    attempt = db_session.query(Attempt).filter(Attempt.id == attempt_id).one()
    rating, event = ratings.apply_rated_attempt(
        db_session,
        user_id=owner.id,
        exercise_slug=SLUG,
        attempt=attempt,
        result=attempt.result,
        puzzle_rating=puzzle.initial_rating,
    )
    db_session.commit()

    after = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert after == before
    assert rating.rating == before["rating"]
    assert db_session.query(RatingEvent).filter(RatingEvent.attempt_id == attempt_id).count() == 1
    assert event.id is not None


def test_duplicate_event_for_same_attempt_violates_constraint(db_session):
    from sqlalchemy.exc import IntegrityError

    event = RatingEvent(
        user_id=1, exercise_slug="piece-recognition", attempt_id=424242,
        rating_before=1200.0, rating_delta=1.0, rating_after=1201.0,
        rating_deviation_before=350.0, rating_deviation_after=339.5, reason="attempt",
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(
        RatingEvent(
            user_id=1, exercise_slug="piece-recognition", attempt_id=424242,
            rating_before=1201.0, rating_delta=1.0, rating_after=1202.0,
            rating_deviation_before=339.5, rating_deviation_after=329.3, reason="attempt",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_one_rating_per_user_and_exercise_is_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        PlayerRating(user_id=7, exercise_slug="pin", rating=1200.0, rating_deviation=350.0)
    )
    db_session.commit()
    db_session.add(
        PlayerRating(user_id=7, exercise_slug="pin", rating=1300.0, rating_deviation=300.0)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ownership --------------------------------------------------------------------


def test_ratings_are_strictly_owned(client, db_session):
    alice = _token(client, "alice_r")
    bob = _token(client, "bob_r")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    _submit(client, alice, puzzle.id, _correct_answer(puzzle))

    assert client.get("/api/v1/me/ratings", headers=_bearer(bob)).json() == {"items": []}
    foreign = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(bob))
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "RATING_NOT_FOUND"
    foreign_history = client.get(f"/api/v1/me/ratings/{SLUG}/history", headers=_bearer(bob))
    assert foreign_history.status_code == 200
    assert foreign_history.json() == {"items": []}

    own = client.get("/api/v1/me/ratings", headers=_bearer(alice)).json()
    assert len(own["items"]) == 1


# --- independence -------------------------------------------------------------------


def test_exercise_ratings_are_independent(client, db_session):
    token = _token(client, "rater_multi")
    piece_puzzle = _seeded_piece_puzzle(db_session)
    legal_puzzle = _seeded_legal_puzzle(db_session)
    from app.modules.legal_destinations.validator import SLUG as LEGAL_SLUG
    from app.modules.piece_recognition.validator import SLUG as PIECE_SLUG

    piece_before = _submit(client, token, piece_puzzle.id, _correct_answer(piece_puzzle)).json()
    _submit(client, token, legal_puzzle.id, {"selected_squares": []})

    piece = client.get(f"/api/v1/me/ratings/{PIECE_SLUG}", headers=_bearer(token)).json()
    legal = client.get(f"/api/v1/me/ratings/{LEGAL_SLUG}", headers=_bearer(token)).json()
    # Legal-destinations activity created its own row and left the other untouched.
    assert piece["rating"] == piece_before["rating_after"]
    assert piece["attempts_count"] == 1
    assert legal["attempts_count"] == 1
    listed = client.get("/api/v1/me/ratings", headers=_bearer(token)).json()
    assert sorted(row["exercise"] for row in listed["items"]) == [LEGAL_SLUG, PIECE_SLUG]


def test_external_chess_ratings_stay_separate_from_microchess_ratings(client, db_session):
    token = _token(client, "rater_ext")
    headers = _bearer(token)
    puzzle = _seeded_piece_puzzle(db_session)

    added = client.post(
        "/api/v1/me/chess-identities",
        json={"provider": "lichess", "username": "ext_acc", "rating": 2050},
        headers=headers,
    )
    assert added.status_code == 201

    # Self-reported external rating creates no MicroChess rating.
    assert client.get("/api/v1/me/ratings", headers=headers).json() == {"items": []}
    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    from app.modules.piece_recognition.validator import SLUG

    current = client.get(f"/api/v1/me/ratings/{SLUG}", headers=headers).json()
    assert current["rating"] != 2050


# --- historical data ------------------------------------------------------------------


def test_phase3_attempts_do_not_gain_fabricated_rating_events(client, db_session):
    token = _token(client, "rater_legacy")
    puzzle = _seeded_piece_puzzle(db_session)

    practice = _submit(client, token, puzzle.id, _correct_answer(puzzle), mode="practice")
    assert db_session.query(RatingEvent).count() == 0
    # Legacy/practice history stays exactly as recorded: no rating snapshot.
    assert practice.json()["rating_before"] is None
    assert practice.json()["rating_delta"] is None
    assert practice.json()["rating_after"] is None


# --- migration ------------------------------------------------------------------------


def _v3_style_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import_models()
    # Phase 3 shape: everything except the Phase 4 tables and the new
    # attempt snapshot columns (SQLite supports DROP COLUMN here).
    tables = [
        table
        for name, table in Base.metadata.tables.items()
        if name
        not in (
            "player_ratings",
            "rating_events",
            "player_gamification_state",
            "xp_events",
            "player_streaks",
            "player_achievements",
        )
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE attempts DROP COLUMN rating_before"))
        conn.execute(text("ALTER TABLE attempts DROP COLUMN rating_after"))
        conn.execute(text("ALTER TABLE attempts DROP COLUMN xp_awarded"))
        conn.execute(text("DELETE FROM schema_version"))
        conn.execute(
            text("INSERT INTO schema_version (version, applied_at) VALUES (3, '2026-01-01T00:00:00')")
        )
    return engine


def test_phase3_database_upgrades_to_v6_preserving_data():
    from app.modules.exercises.models import Exercise
    from app.modules.progress.models import Attempt
    from app.modules.puzzles.models import Puzzle
    from app.modules.users.models import User

    engine = _v3_style_engine()
    session = sessionmaker(bind=engine)()
    session.add(User(username="legacy", password_hash="x", display_name="Legacy"))
    session.add(
        Exercise(slug="piece-recognition", title_fa="تشخیص مهره", title_en="", description="")
    )
    session.commit()
    user_id = session.query(User).filter(User.username == "legacy").one().id
    session.add(
        Puzzle(
            exercise_slug="piece-recognition", answer_json={"squares": ["a1"]},
            is_published=True, initial_rating=800.0,
        )
    )
    session.commit()
    puzzle_id = session.query(Puzzle).first().id
    session.commit()
    session.close()
    # The legacy attempt is written with the v3 column set (raw SQL), the
    # way a real Phase 3 database would hold it.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO attempts (user_id, puzzle_id, exercise_slug, mode, result, "
                "answer_json, score, rating_delta, hints_used, created_at) "
                "VALUES (:u, :p, 'piece-recognition', 'practice', 'correct', "
                "'{}', 1.0, NULL, '[]', '2026-01-01T00:00:00')"
            ),
            {"u": user_id, "p": puzzle_id},
        )

    assert ensure_schema(engine) == SCHEMA_VERSION == 8
    assert ensure_schema(engine) == 8  # idempotent re-run

    names = inspect(engine).get_table_names()
    assert "player_ratings" in names
    assert "rating_events" in names
    cols = {c["name"] for c in inspect(engine).get_columns("attempts")}
    assert {"rating_before", "rating_delta", "rating_after", "xp_awarded"} <= cols

    session = sessionmaker(bind=engine)()
    try:
        assert session.query(User).filter(User.username == "legacy").count() == 1
        assert session.query(Exercise).filter(Exercise.slug == "piece-recognition").count() == 1
        attempt = session.query(Attempt).one()
        assert attempt.result == "correct"
        assert attempt.rating_before is None  # no fabricated history
        assert attempt.xp_awarded is None  # no fabricated XP
        assert session.query(RatingEvent).count() == 0
    finally:
        session.close()
