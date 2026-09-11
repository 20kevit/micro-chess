"""Phase 5 gamification: server-authoritative XP, levels, streaks, achievements.

Covers XP calculation/persistence/history, practice+rated eligibility,
idempotent reprocessing, level transitions, UTC streak behavior,
achievement unlocks, ownership, guest exclusion, rating independence,
and the v4 -> v5 migration.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.migration import SCHEMA_VERSION, ensure_schema, import_models
from app.modules.gamification_engine import service as gamification
from app.modules.gamification_engine.models import (
    PlayerAchievement,
    PlayerGamificationState,
    PlayerStreak,
    XpEvent,
)


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


def _submit(client, token, puzzle_id, answer, mode="practice"):
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


# --- pure rules -----------------------------------------------------------------


def test_xp_amounts_are_exact_and_terminal_states_rejected():
    assert gamification.xp_for_result("correct") == 10
    assert gamification.xp_for_result("partial") == 5
    assert gamification.xp_for_result("wrong") == 2
    for terminal in ("timeout", "skipped", "abandoned"):
        with pytest.raises(ValueError):
            gamification.xp_for_result(terminal)


def test_level_boundaries_are_exact():
    assert gamification.level_for_total(0) == 1
    assert gamification.level_for_total(99) == 1
    assert gamification.level_for_total(100) == 2
    assert gamification.level_for_total(199) == 2
    assert gamification.level_for_total(200) == 3
    assert gamification.xp_progress_in_level(0) == (0, 100)
    assert gamification.xp_progress_in_level(130) == (30, 100)
    assert gamification.xp_progress_in_level(200) == (0, 100)


def test_xp_eligibility_is_mode_independent_but_guest_and_terminal_excluded():
    assert gamification.is_xp_eligible(user_id=1, result="correct") is True
    assert gamification.is_xp_eligible(user_id=1, result="partial") is True
    assert gamification.is_xp_eligible(user_id=1, result="wrong") is True
    assert gamification.is_xp_eligible(user_id=1, result="timeout") is False
    assert gamification.is_xp_eligible(user_id=1, result="skipped") is False
    assert gamification.is_xp_eligible(user_id=1, result="abandoned") is False
    assert gamification.is_xp_eligible(user_id=None, result="correct") is False


# --- XP via the attempt flow ----------------------------------------------------


def test_first_practice_attempt_awards_xp_and_stamps_attempt(client, db_session):
    token = _token(client, "xp_first")
    puzzle = _seeded_piece_puzzle(db_session)

    res = _submit(client, token, puzzle.id, _correct_answer(puzzle), mode="practice")
    assert res.status_code == 200
    assert res.json()["result"] == "correct"
    assert res.json()["xp_awarded"] == 10

    from app.modules.progress.models import Attempt

    attempt = db_session.query(Attempt).one()
    assert attempt.xp_awarded == 10

    event = db_session.query(XpEvent).one()
    assert event.amount == 10
    assert event.reason == "attempt"
    assert event.attempt_id == attempt.id
    assert event.balance_after == 10

    state = db_session.query(PlayerGamificationState).one()
    assert state.total_xp == 10
    assert state.level == 1


def test_rated_attempt_also_earns_xp_without_touching_rating_rules(client, db_session):
    token = _token(client, "xp_rated")
    puzzle = _seeded_piece_puzzle(db_session)

    res = _submit(client, token, puzzle.id, _wrong_answer(), mode="rated")
    assert res.json()["xp_awarded"] == 2
    assert res.json()["rating_delta"] is not None  # rating still behaves per Phase 4

    summary = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert summary["xp"] == {"total": 2, "level": 1, "xp_in_level": 2, "xp_for_next": 100}


def test_xp_accumulates_and_level_transitions_at_100(client, db_session):
    token = _token(client, "xp_level")
    puzzle = _seeded_piece_puzzle(db_session)

    for _ in range(10):  # 10 correct x 10 XP = 100 XP
        assert _submit(client, token, puzzle.id, _correct_answer(puzzle)).status_code == 200

    summary = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert summary["xp"]["total"] == 100
    assert summary["xp"]["level"] == 2
    assert summary["xp"]["xp_in_level"] == 0

    state = db_session.query(PlayerGamificationState).one()
    assert state.total_xp == 100
    assert state.level == 2
    # Ledger stays the source of truth: sum of events equals the projection.
    total = sum(e.amount for e in db_session.query(XpEvent).all())
    assert total == state.total_xp == 100


def test_partial_and_wrong_amounts_through_the_api(client, db_session):
    token = _token(client, "xp_mixed")
    puzzle = _seeded_piece_puzzle(db_session)

    assert _submit(client, token, puzzle.id, _partial_answer(puzzle)).json()["xp_awarded"] == 5
    assert _submit(client, token, puzzle.id, _wrong_answer()).json()["xp_awarded"] == 2

    summary = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert summary["xp"]["total"] == 7


def test_terminal_submission_earns_no_xp(client, db_session):
    token = _token(client, "xp_timeout")
    puzzle = _seeded_piece_puzzle(db_session)

    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "practice", "client_result": "timeout"},
        headers=_bearer(token),
    )
    assert res.json()["result"] == "timeout"
    assert res.json()["xp_awarded"] is None
    assert db_session.query(XpEvent).count() == 0
    assert db_session.query(PlayerGamificationState).count() == 0


def test_guest_attempt_creates_no_persistent_gamification(client, db_session):
    puzzle = _seeded_piece_puzzle(db_session)
    guest_token = client.post("/api/v1/guest/session").json()["guest_token"]
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": _correct_answer(puzzle), "mode": "practice"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert res.status_code == 200
    assert res.json()["xp_awarded"] is None
    assert db_session.query(XpEvent).count() == 0
    assert db_session.query(PlayerGamificationState).count() == 0
    assert db_session.query(PlayerStreak).count() == 0
    assert db_session.query(PlayerAchievement).count() == 0


# --- idempotency ------------------------------------------------------------------


def test_reprocessing_same_attempt_does_not_double_award(client, db_session):
    token = _token(client, "xp_idem")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.progress.models import Attempt
    from app.modules.users.models import User

    attempt_id = _submit(client, token, puzzle.id, _correct_answer(puzzle)).json()["id"]
    owner = db_session.query(User).filter(User.username == "xp_idem").one()
    before = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()

    attempt = db_session.query(Attempt).filter(Attempt.id == attempt_id).one()
    event = gamification.apply_attempt(
        db_session,
        user_id=owner.id,
        attempt=attempt,
        result=attempt.result,
        active_date=date(2026, 9, 11),
    )
    db_session.commit()

    after = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert after == before
    assert event.amount == 10
    assert db_session.query(XpEvent).filter(XpEvent.attempt_id == attempt_id).count() == 1


def test_duplicate_event_for_same_attempt_violates_constraint(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        XpEvent(user_id=1, amount=10, reason="attempt", attempt_id=424243, balance_after=10)
    )
    db_session.commit()
    db_session.add(
        XpEvent(user_id=1, amount=10, reason="attempt", attempt_id=424243, balance_after=20)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_one_gamification_state_per_user_is_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(PlayerGamificationState(user_id=7, total_xp=0, level=1))
    db_session.commit()
    db_session.add(PlayerGamificationState(user_id=7, total_xp=5, level=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- streaks ------------------------------------------------------------------------


def test_streak_first_day_second_day_same_day_and_missed_day(db_session):
    row = gamification.update_streak(db_session, user_id=11, active_date=date(2026, 9, 1))
    assert (row.current_streak, row.longest_streak) == (1, 1)

    # Repeated activity on the same UTC date is a no-op.
    row = gamification.update_streak(db_session, user_id=11, active_date=date(2026, 9, 1))
    assert (row.current_streak, row.longest_streak) == (1, 1)

    # Consecutive day extends.
    row = gamification.update_streak(db_session, user_id=11, active_date=date(2026, 9, 2))
    assert (row.current_streak, row.longest_streak) == (2, 2)

    # Missed day resets current but preserves longest.
    row = gamification.update_streak(db_session, user_id=11, active_date=date(2026, 9, 4))
    assert (row.current_streak, row.longest_streak) == (1, 2)
    assert row.last_qualified_date == date(2026, 9, 4)


def test_streak_longest_survives_and_reprocessing_is_idempotent(client, db_session):
    from datetime import timedelta
    from app.modules.users.models import User

    token = _token(client, "xp_streak")
    puzzle = _seeded_piece_puzzle(db_session)
    owner = db_session.query(User).filter(User.username == "xp_streak").one()

    # The submission above marks today (server UTC date); extend with the
    # next two consecutive UTC dates so the test never depends on the
    # calendar day it runs on.
    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    today = date.today()
    gamification.update_streak(db_session, user_id=owner.id, active_date=today + timedelta(days=1))
    gamification.update_streak(db_session, user_id=owner.id, active_date=today + timedelta(days=2))
    db_session.commit()

    summary = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert summary["streak"] == {"current": 3, "longest": 3}

    # Replaying the same date never extends twice.
    gamification.update_streak(db_session, user_id=owner.id, active_date=today + timedelta(days=2))
    db_session.commit()
    again = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert again["streak"] == {"current": 3, "longest": 3}


def test_streak_date_boundary_uses_utc_dates(db_session):
    # Consecutive UTC dates extend even across a month boundary.
    gamification.update_streak(db_session, user_id=12, active_date=date(2026, 8, 31))
    row = gamification.update_streak(db_session, user_id=12, active_date=date(2026, 9, 1))
    assert (row.current_streak, row.longest_streak) == (2, 2)


# --- achievements ---------------------------------------------------------------------


def test_achievement_locked_then_unlocked_exactly_once(client, db_session):
    token = _token(client, "xp_ach")
    puzzle = _seeded_piece_puzzle(db_session)
    headers = _bearer(token)

    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    assert [item["code"] for item in catalog["items"]] == [
        "first_steps",
        "steady_10",
        "xp_100",
        "streak_3",
    ]
    assert all(item["unlocked"] is False for item in catalog["items"])

    _submit(client, token, puzzle.id, _correct_answer(puzzle))

    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    first = next(item for item in catalog["items"] if item["code"] == "first_steps")
    assert first["unlocked"] is True
    assert first["unlocked_at"]
    rest = [item for item in catalog["items"] if item["code"] != "first_steps"]
    assert all(item["unlocked"] is False for item in rest)

    # Repeated evaluation stays idempotent: still exactly one unlock row.
    from app.modules.users.models import User

    owner = db_session.query(User).filter(User.username == "xp_ach").one()
    gamification.evaluate_achievements(db_session, user_id=owner.id)
    db_session.commit()
    assert (
        db_session.query(PlayerAchievement)
        .filter(
            PlayerAchievement.user_id == owner.id,
            PlayerAchievement.achievement_code == "first_steps",
        )
        .count()
        == 1
    )


def test_steady_10_unlocks_on_tenth_qualifying_attempt(client, db_session):
    token = _token(client, "xp_steady")
    puzzle = _seeded_piece_puzzle(db_session)
    headers = _bearer(token)

    for _ in range(9):
        _submit(client, token, puzzle.id, _correct_answer(puzzle))
    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    steady = next(item for item in catalog["items"] if item["code"] == "steady_10")
    assert steady["unlocked"] is False

    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    steady = next(item for item in catalog["items"] if item["code"] == "steady_10")
    assert steady["unlocked"] is True
    xp100 = next(item for item in catalog["items"] if item["code"] == "xp_100")
    assert xp100["unlocked"] is True  # 10 x 10 XP hits the XP milestone too


def test_streak_3_unlocks_on_third_consecutive_day(client, db_session):
    from datetime import timedelta
    from app.modules.users.models import User

    token = _token(client, "xp_streak3")
    puzzle = _seeded_piece_puzzle(db_session)
    headers = _bearer(token)
    owner = db_session.query(User).filter(User.username == "xp_streak3").one()

    # The submission marks today (server UTC date); build forward from it.
    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    today = date.today()
    gamification.update_streak(db_session, user_id=owner.id, active_date=today + timedelta(days=1))
    db_session.commit()
    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    assert next(i for i in catalog["items"] if i["code"] == "streak_3")["unlocked"] is False

    gamification.update_streak(db_session, user_id=owner.id, active_date=today + timedelta(days=2))
    unlocked = gamification.evaluate_achievements(db_session, user_id=owner.id)
    db_session.commit()
    assert [row.achievement_code for row in unlocked] == ["streak_3"]
    catalog = client.get("/api/v1/me/achievements", headers=headers).json()
    assert next(i for i in catalog["items"] if i["code"] == "streak_3")["unlocked"] is True


def test_duplicate_unlock_violates_constraint(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(PlayerAchievement(user_id=3, achievement_code="first_steps"))
    db_session.commit()
    db_session.add(PlayerAchievement(user_id=3, achievement_code="first_steps"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- API: history, ownership, security --------------------------------------------------


def test_xp_history_is_newest_first_and_explains_balance(client, db_session):
    token = _token(client, "xp_hist")
    puzzle = _seeded_piece_puzzle(db_session)
    headers = _bearer(token)

    first = _submit(client, token, puzzle.id, _correct_answer(puzzle)).json()
    second = _submit(client, token, puzzle.id, _wrong_answer()).json()

    history = client.get("/api/v1/me/gamification/xp", headers=headers).json()
    assert [item["attempt_id"] for item in history["items"]] == [second["id"], first["id"]]
    assert set(history["items"][0]) == {
        "attempt_id",
        "amount",
        "reason",
        "balance_after",
        "occurred_at",
    }
    assert history["items"][0]["amount"] == 2
    assert history["items"][0]["balance_after"] == 12
    assert history["items"][1]["amount"] == 10
    assert history["items"][1]["balance_after"] == 10


def test_gamification_endpoints_require_authentication(client):
    for path in [
        "/api/v1/me/gamification",
        "/api/v1/me/gamification/xp",
        "/api/v1/me/achievements",
    ]:
        res = client.get(path)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "AUTH_REQUIRED"


def test_gamification_state_is_strictly_owned(client, db_session):
    alice = _token(client, "alice_g")
    bob = _token(client, "bob_g")
    puzzle = _seeded_piece_puzzle(db_session)

    _submit(client, alice, puzzle.id, _correct_answer(puzzle))

    assert client.get("/api/v1/me/gamification", headers=_bearer(bob)).json()["xp"]["total"] == 0
    assert client.get("/api/v1/me/gamification/xp", headers=_bearer(bob)).json() == {"items": []}
    assert all(
        item["unlocked"] is False
        for item in client.get("/api/v1/me/achievements", headers=_bearer(bob)).json()["items"]
    )
    assert client.get("/api/v1/me/gamification", headers=_bearer(alice)).json()["xp"]["total"] == 10


def test_gamification_has_no_client_write_endpoints(client, db_session):
    token = _token(client, "xp_locked")
    puzzle = _seeded_piece_puzzle(db_session)
    _submit(client, token, puzzle.id, _correct_answer(puzzle))
    headers = _bearer(token)
    # No client-facing mutation endpoint for XP, streaks, or achievements.
    assert client.post("/api/v1/me/gamification", headers=headers).status_code == 405
    assert client.post("/api/v1/me/gamification/xp", headers=headers).status_code == 405
    assert client.post("/api/v1/me/achievements", headers=headers).status_code == 405
    assert client.patch("/api/v1/me/gamification", headers=headers).status_code == 405
    assert client.delete("/api/v1/me/gamification", headers=headers).status_code == 405


def test_new_player_has_correct_initial_state(client):
    token = _token(client, "xp_new")
    headers = _bearer(token)
    summary = client.get("/api/v1/me/gamification", headers=headers).json()
    assert summary == {
        "xp": {"total": 0, "level": 1, "xp_in_level": 0, "xp_for_next": 100},
        "streak": {"current": 0, "longest": 0},
        "achievements_unlocked": 0,
        "total_achievements": 4,
    }
    assert client.get("/api/v1/me/gamification/xp", headers=headers).json() == {"items": []}


# --- integration: ratings untouched, no backfill -------------------------------------------


def test_gamification_and_ratings_share_attempt_transaction_but_rules_stay_separate(
    client, db_session
):
    from app.modules.piece_recognition.validator import SLUG

    token = _token(client, "xp_ratings")
    puzzle = _seeded_piece_puzzle(db_session)

    # Practice: XP yes, rating no.
    practice = _submit(client, token, puzzle.id, _correct_answer(puzzle), mode="practice").json()
    assert practice["xp_awarded"] == 10
    assert practice["rating_delta"] is None

    # Rated: XP and rating both move.
    rated = _submit(client, token, puzzle.id, _correct_answer(puzzle), mode="rated").json()
    assert rated["xp_awarded"] == 10
    assert rated["rating_delta"] is not None
    assert rated["rating_after"] == pytest.approx(rated["rating_before"] + rated["rating_delta"])

    current = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert current["rating"] == rated["rating_after"]
    summary = client.get("/api/v1/me/gamification", headers=_bearer(token)).json()
    assert summary["xp"]["total"] == 20


def test_historical_attempts_gain_no_fabricated_xp(client, db_session):
    token = _token(client, "xp_legacy")
    puzzle = _seeded_piece_puzzle(db_session)

    # Terminal history stays exactly as recorded: no XP snapshot.
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "practice", "client_result": "skipped"},
        headers=_bearer(token),
    )
    assert res.json()["xp_awarded"] is None
    assert db_session.query(XpEvent).count() == 0


# --- migration -------------------------------------------------------------------------------


def _v4_style_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import_models()
    # Phase 4 shape: everything except the Phase 5 tables and the new
    # attempt XP snapshot column (SQLite supports DROP COLUMN here).
    tables = [
        table
        for name, table in Base.metadata.tables.items()
        if name
        not in (
            "player_gamification_state",
            "xp_events",
            "player_streaks",
            "player_achievements",
        )
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE attempts DROP COLUMN xp_awarded"))
        conn.execute(text("DELETE FROM schema_version"))
        conn.execute(
            text("INSERT INTO schema_version (version, applied_at) VALUES (4, '2026-01-01T00:00:00')")
        )
    return engine


def test_phase4_database_upgrades_to_v6_preserving_data():
    from app.modules.exercises.models import Exercise
    from app.modules.progress.models import Attempt
    from app.modules.puzzles.models import Puzzle
    from app.modules.rating_engine.models import PlayerRating, RatingEvent
    from app.modules.users.models import User

    engine = _v4_style_engine()
    session = sessionmaker(bind=engine)()
    session.add(User(username="legacy5", password_hash="x", display_name="Legacy5"))
    session.add(
        Exercise(slug="piece-recognition", title_fa="تشخیص مهره", title_en="", description="")
    )
    session.commit()
    user_id = session.query(User).filter(User.username == "legacy5").one().id
    session.add(
        Puzzle(
            exercise_slug="piece-recognition",
            answer_json={"squares": ["a1"]},
            is_published=True,
            initial_rating=800.0,
        )
    )
    session.commit()
    puzzle_id = session.query(Puzzle).first().id
    session.commit()
    session.close()
    # Legacy rows are written with the v4 column set (raw SQL), the way a
    # real Phase 4 database would hold them.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO attempts (user_id, puzzle_id, exercise_slug, mode, result, "
                "answer_json, score, rating_before, rating_delta, rating_after, "
                "hints_used, created_at) "
                "VALUES (:u, :p, 'piece-recognition', 'rated', 'correct', "
                "'{}', 1.0, 1200.0, 8.0, 1208.0, '[]', '2026-01-01T00:00:00')"
            ),
            {"u": user_id, "p": puzzle_id},
        )

    assert ensure_schema(engine) == SCHEMA_VERSION == 8
    assert ensure_schema(engine) == 8  # idempotent re-run

    names = inspect(engine).get_table_names()
    assert "player_gamification_state" in names
    assert "xp_events" in names
    assert "player_streaks" in names
    assert "player_achievements" in names
    cols = {c["name"] for c in inspect(engine).get_columns("attempts")}
    assert "xp_awarded" in cols

    session = sessionmaker(bind=engine)()
    try:
        assert session.query(User).filter(User.username == "legacy5").count() == 1
        attempt = session.query(Attempt).one()
        assert attempt.result == "correct"
        assert attempt.rating_after == 1208.0  # Phase 4 history survives
        assert attempt.xp_awarded is None  # no fabricated XP
        assert session.query(PlayerRating).count() == 0
        assert session.query(RatingEvent).count() == 0
        assert session.query(XpEvent).count() == 0
        assert session.query(PlayerGamificationState).count() == 0
    finally:
        session.close()
