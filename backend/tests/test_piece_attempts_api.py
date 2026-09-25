"""Piece Recognition API flow: submit, attempts, hints, modes, timing."""

from datetime import datetime, timedelta, timezone

from app.modules.users.models import User
from app.modules.piece_recognition import seed as seed_mod
from app.modules.piece_recognition.validator import SLUG
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from tests.conftest import publish_staged_puzzles


def _seeded_puzzle(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG)
        .order_by(Puzzle.id)
        .first()
    )
    assert puzzle is not None
    return puzzle


def _auth_header(db_session) -> dict[str, str]:
    # Insert directly to avoid the passlib/bcrypt env issue; this test only
    # needs an authenticated user id, not password verification. The token
    # is bound to a real server-side session (Phase 2 revocation model).
    from app.modules.auth import service as auth_service

    user = User(username="kid", email="kid@example.com", password_hash="not-verified", display_name="Kid")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _, token = auth_service.create_user_session(db_session, user, "PLAYER")
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}


def test_puzzle_list_hides_answer_but_shows_prompt(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    first = body[0]
    assert first["prompt_fa"]
    assert first["explanation"]
    assert "answer_json" not in first
    assert first["fen"] == puzzle.fen


def test_puzzle_detail_and_404(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert res.json()["prompt_fa"] == puzzle.prompt_fa
    assert "answer_json" not in res.json()
    assert client.get("/api/v1/puzzles/999999").status_code == 404


def test_practice_submit_correct_records_attempt(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    res = client.post(
        "/api/v1/attempts",
        headers=_auth_header(db_session),
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "practice",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "correct"
    # Per-square scoring: +5 per correct target, no misses/wrongs here.
    assert body["score"] == 5.0 * len(puzzle.answer_json["squares"])
    assert body["rating_delta"] is None
    assert body["detail"]["missed"] == [] and body["detail"]["wrong"] == []

    attempt = db_session.query(Attempt).filter(Attempt.id == body["id"]).one()
    assert attempt.answer_json == {"selected_squares": puzzle.answer_json["squares"]}
    assert attempt.hints_used == []
    assert attempt.mode == "practice"


def test_partial_per_square_scoring(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    squares = puzzle.answer_json["squares"]
    assert len(squares) >= 2
    res = client.post(
        "/api/v1/attempts",
        headers=_auth_header(db_session),
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": squares[:1]}, "mode": "practice"},
    )
    assert res.json()["result"] == "partial"
    # 1 correct (+5), rest missed (-1 each), nothing wrong.
    assert res.json()["score"] == 5.0 - (len(squares) - 1)


def test_rated_requires_auth(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert res.status_code == 401


def test_rated_with_auth_updates_player_rating(client, db_session):
    from app.modules.rating_engine.models import PlayerRating, RatingEvent

    puzzle = _seeded_puzzle(db_session)
    headers = _auth_header(db_session)
    res = client.post(
        "/api/v1/attempts",
        headers=headers,
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "rated",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "correct"
    # Phase 4: a correct rated attempt moves the rating server-side.
    assert body["rating_before"] == 1200.0
    assert body["rating_delta"] is not None and body["rating_delta"] > 0
    assert body["rating_after"] == body["rating_before"] + body["rating_delta"]
    attempt = db_session.query(Attempt).filter(Attempt.id == body["id"]).one()
    assert attempt.user_id is not None
    assert attempt.mode == "rated"
    assert attempt.rating_before == body["rating_before"]
    assert attempt.rating_delta == body["rating_delta"]
    assert attempt.rating_after == body["rating_after"]

    rating = (
        db_session.query(PlayerRating)
        .filter(
            PlayerRating.user_id == attempt.user_id,
            PlayerRating.exercise_slug == SLUG,
        )
        .one()
    )
    assert rating.rating == body["rating_after"]
    assert rating.games_count == 1
    assert rating.is_provisional is True

    event = db_session.query(RatingEvent).filter(RatingEvent.attempt_id == attempt.id).one()
    assert event.user_id == attempt.user_id
    assert event.exercise_slug == SLUG
    assert event.rating_before == body["rating_before"]
    assert event.rating_delta == body["rating_delta"]
    assert event.rating_after == body["rating_after"]
    assert event.reason == "attempt"


def test_hints_and_timing_recorded(client, db_session):
    puzzle = _seeded_puzzle(db_session)
    started = (datetime.now(timezone.utc) - timedelta(seconds=42)).isoformat()
    res = client.post(
        "/api/v1/attempts",
        headers=_auth_header(db_session),
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": []},
            "mode": "practice",
            "hints_used": ["h1"],
            "started_at": started,
            "client_result": None,
        },
    )
    body = res.json()
    assert body["hints_used"] == ["h1"]
    assert body["duration_ms"] is not None and body["duration_ms"] >= 40000
    attempt = db_session.query(Attempt).filter(Attempt.id == body["id"]).one()
    assert attempt.hints_used == ["h1"]
    assert attempt.duration_ms is not None
    assert attempt.started_at is not None
