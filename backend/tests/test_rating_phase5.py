"""Phase 5 rating alignment: lock official policy behavior with minimal tests.

Authoritative sources (repo reality 2026-09-19):
- docs/platform/training/RATINGS.md + PHASE_04_RATINGS.md
- docs/DECISIONS.md (DEC-005 external separate, DEC-014 interim Elo, DEC-016 guest gate)
- docs/platform/DATA_MODEL.md + AGENTS.md (practice MUST NOT set rating_delta)
- backend/app/modules/rating_engine/service.py (single documented source)

NOTE: docs/RATING_POLICY.md and ADR-001-rating-as-internal-calibration-engine.md
do not exist in this repo, so no behavior is derived from them. Where the Phase 5
brief conflicts with the authoritative docs (practice-as-rating-channel,
hide-ratings-from-user, mutable puzzle rating), this file locks the documented
behavior instead: rated mode is the channel, /me/ratings stays player-visible
(Phase 4 DoD + analytics depend on it), Puzzle.initial_rating is static opponent
calibration (observed difficulty lives in analytics, never rewrites puzzles).
No new formula or threshold is introduced here.
"""

import pytest

from app.modules.rating_engine import service as ratings
from app.modules.rating_engine.models import PlayerRating, RatingEvent
from app.modules.rule_engine.base import AttemptMode


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
    from tests.conftest import publish_staged_puzzles

    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
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


# --- 1. eligibility -----------------------------------------------------------

def test_eligibility_matrix():
    assert ratings.is_rating_eligible(mode=AttemptMode.RATED, user_id=1, result="correct")
    assert ratings.is_rating_eligible(mode=AttemptMode.RATED, user_id=1, result="partial")
    assert ratings.is_rating_eligible(mode=AttemptMode.RATED, user_id=1, result="wrong")
    # Practice never rates (AGENTS.md + RATINGS §7).
    assert not ratings.is_rating_eligible(mode=AttemptMode.PRACTICE, user_id=1, result="correct")
    # Guests never rate (DEC-016).
    assert not ratings.is_rating_eligible(mode=AttemptMode.RATED, user_id=None, result="correct")
    # Terminal states never rate.
    for terminal in ("timeout", "skipped", "abandoned"):
        assert not ratings.is_rating_eligible(mode=AttemptMode.RATED, user_id=1, result=terminal)


# --- 2. user/puzzle separation -------------------------------------------------

def test_rated_attempt_moves_user_rating_but_never_puzzle_rating(client, db_session):
    token = _token(client, "p5_sep")
    puzzle = _seeded_piece_puzzle(db_session)
    before_puzzle_rating = puzzle.initial_rating

    res = _submit(client, token, puzzle.id, {"selected_squares": list(puzzle.answer_json["squares"])})
    assert res.status_code == 200
    assert res.json()["rating_delta"] is not None

    db_session.refresh(puzzle)
    assert puzzle.initial_rating == before_puzzle_rating  # puzzle calibration is static
    assert db_session.query(PlayerRating).count() == 1


# --- 3. practice vs speed ------------------------------------------------------

def test_practice_rates_nothing_and_speed_mode_is_rejected(client, db_session):
    token = _token(client, "p5_modes")
    puzzle = _seeded_piece_puzzle(db_session)

    practice = _submit(
        client, token, puzzle.id,
        {"selected_squares": list(puzzle.answer_json["squares"])}, mode="practice",
    )
    assert practice.json()["rating_delta"] is None
    assert db_session.query(PlayerRating).count() == 0
    assert db_session.query(RatingEvent).count() == 0

    # No speed mode exists in AttemptMode: it cannot rate, it cannot even submit.
    speed = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "speed"},
        headers=_bearer(token),
    )
    assert speed.status_code == 422
    assert db_session.query(RatingEvent).count() == 0


# --- 4. new user uncertainty ----------------------------------------------------

def test_new_user_starts_uncertain_and_provisional(client, db_session):
    assert ratings.INITIAL_RD == 350.0  # high uncertainty for new users
    token = _token(client, "p5_new")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    _submit(client, token, puzzle.id, {"selected_squares": list(puzzle.answer_json["squares"])})
    detail = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    assert detail["provisional"] is True
    assert detail["attempts_count"] == 1
    assert detail["rating_deviation"] < ratings.INITIAL_RD  # decay started, still high
    assert detail["rating_deviation"] >= ratings.RD_MIN


# --- 5. win/loss/draw ------------------------------------------------------------

def test_win_draw_loss_ordering():
    win = ratings.calculate_update(
        rating_before=1200.0, rd_before=350.0, games_before=0, score=1.0, opponent_rating=1200.0)
    draw = ratings.calculate_update(
        rating_before=1200.0, rd_before=350.0, games_before=0, score=0.5, opponent_rating=1200.0)
    loss = ratings.calculate_update(
        rating_before=1200.0, rd_before=350.0, games_before=0, score=0.0, opponent_rating=1200.0)
    assert win.rating_delta > 0
    assert loss.rating_delta < 0
    assert win.rating_delta > draw.rating_delta > loss.rating_delta
    assert draw.rating_delta == pytest.approx(0.0)  # equal strength draw holds rating


# --- 6. difficulty ------------------------------------------------------------------

def test_harder_opponent_moves_rating_more_on_win():
    easy = ratings.calculate_update(
        rating_before=1200.0, rd_before=350.0, games_before=5, score=1.0, opponent_rating=800.0)
    hard = ratings.calculate_update(
        rating_before=1200.0, rd_before=350.0, games_before=5, score=1.0, opponent_rating=1600.0)
    assert hard.rating_delta > easy.rating_delta > 0


# --- 7. history audit ------------------------------------------------------------------

def test_history_event_is_complete_and_auditable(client, db_session):
    token = _token(client, "p5_hist")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    first = _submit(client, token, puzzle.id, {"selected_squares": list(puzzle.answer_json["squares"])}).json()
    items = client.get(f"/api/v1/me/ratings/{SLUG}/history", headers=_bearer(token)).json()["items"]
    assert len(items) == 1
    event = items[0]
    assert event["attempt_id"] == first["id"]
    assert event["after"] == pytest.approx(event["before"] + event["delta"])
    assert event["reason"] == "attempt"
    assert event["rating_deviation_after"] < event["rating_deviation_before"]
    assert event["occurred_at"]
    row = db_session.query(RatingEvent).one()
    assert (row.rating_before, row.rating_delta, row.rating_after) == (
        event["before"], event["delta"], event["after"])


# --- 8. idempotency -----------------------------------------------------------------------

def test_reapply_same_attempt_is_idempotent(client, db_session):
    token = _token(client, "p5_idem")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.progress.models import Attempt
    from app.modules.users.models import User

    attempt_id = _submit(
        client, token, puzzle.id, {"selected_squares": list(puzzle.answer_json["squares"])}).json()["id"]
    owner = db_session.query(User).filter(User.username == "p5_idem").one()
    snapshot = client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json()
    attempt = db_session.query(Attempt).filter(Attempt.id == attempt_id).one()
    ratings.apply_rated_attempt(
        db_session, user_id=owner.id, exercise_slug=SLUG, attempt=attempt,
        result=attempt.result, puzzle_rating=puzzle.initial_rating)
    db_session.commit()
    assert client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(token)).json() == snapshot
    assert db_session.query(RatingEvent).filter(RatingEvent.attempt_id == attempt_id).count() == 1


# --- 9. guest blocked -------------------------------------------------------------------------

def test_guest_submit_blocked_with_no_rating_state(client, db_session):
    puzzle = _seeded_piece_puzzle(db_session)
    guest_token = client.post("/api/v1/guest/session").json()["guest_token"]
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "rated"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert res.status_code == 401
    assert db_session.query(PlayerRating).count() == 0
    assert db_session.query(RatingEvent).count() == 0


# --- 10. user isolation ----------------------------------------------------------------------------

def test_user_isolation(client, db_session):
    alice = _token(client, "p5_alice")
    bob = _token(client, "p5_bob")
    puzzle = _seeded_piece_puzzle(db_session)
    from app.modules.piece_recognition.validator import SLUG

    _submit(client, alice, puzzle.id, {"selected_squares": list(puzzle.answer_json["squares"])})
    assert client.get("/api/v1/me/ratings", headers=_bearer(bob)).json() == {"items": []}
    assert client.get(f"/api/v1/me/ratings/{SLUG}", headers=_bearer(bob)).status_code == 404
    assert len(client.get("/api/v1/me/ratings", headers=_bearer(alice)).json()["items"]) == 1
