"""Phase 10 adaptive training: selection policy, eligibility, determinism,
outcomes, authorization, and source-state invariants.

Covers cold start, candidate eligibility (lifecycle + exercise scope),
difficulty matching, performance signals, history/repetition rules,
deterministic seeded selection, fallback, security (player/coach/parent/
revoked/anonymous), outcome recording, and the no-mutation invariant over
attempts/ratings/XP/puzzles.
"""

import random

from app.modules.adaptive import service as adaptive
from app.modules.adaptive.models import AdaptiveRecommendation
from app.modules.exercises.models import Exercise
from app.modules.gamification_engine.models import PlayerGamificationState, XpEvent
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.models import PlayerRating, RatingEvent
from app.modules.users.models import User, UserRole

SLUG = "piece-recognition"
OTHER_SLUG = "captures"


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _user_id(client, token):
    return client.get("/api/v1/users/me", headers=_bearer(token)).json()["id"]


def _grant(db_session, username, role):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, role)) is None:
        db_session.add(UserRole(user_id=user.id, role=role))
        db_session.commit()
    return user


def _ensure_exercise(db_session, slug=SLUG, active=True):
    exercise = db_session.get(Exercise, slug)
    if exercise is None:
        exercise = Exercise(slug=slug, title_fa="x", title_en=slug, is_active=active, sort_order=0)
        db_session.add(exercise)
        db_session.commit()
    else:
        exercise.is_active = active
        db_session.commit()
    return exercise


def _puzzle(db_session, slug=SLUG, rating=1200.0, published=True, archived=False, answer=None):
    _ensure_exercise(db_session, slug)
    puzzle = Puzzle(
        exercise_slug=slug,
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        position_json={},
        answer_json=answer or {"squares": ["a2", "b2"]},
        hint_json={},
        prompt_fa="x",
        initial_rating=rating,
        is_published=published,
        is_archived=archived,
    )
    db_session.add(puzzle)
    db_session.commit()
    db_session.refresh(puzzle)
    return puzzle


def _submit(client, token, puzzle_id, answer, mode="practice"):
    return client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle_id, "answer": answer, "mode": mode},
        headers=_bearer(token),
    )


def _correct(puzzle):
    return {"selected_squares": list(puzzle.answer_json["squares"])}


def _wrong():
    return {"selected_squares": []}


# --- cold start ---------------------------------------------------------------


def test_cold_start_baseline_recommends_content_bearing_exercise(client, db_session):
    token = _token(client, "cold_player")
    _puzzle(db_session, rating=900.0)
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["recommended_exercise"] == SLUG
    assert body["reason"] == "COLD_START"
    assert len(body["exercises"]) == 1
    assert body["exercises"][0]["reason"] == "COLD_START"


def test_cold_start_next_selects_nearest_to_default_ability(client, db_session):
    token = _token(client, "cold_next")
    easy = _puzzle(db_session, rating=800.0)
    mid = _puzzle(db_session, rating=1150.0)
    hard = _puzzle(db_session, rating=2000.0)
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["puzzle"]["id"] == mid.id
    assert body["reason"] == "COLD_START"
    assert body["ability_rating"] == 1200.0
    assert body["target_rating"] == 1200.0
    assert body["fallback"] is False
    assert body["recommendation_id"] > 0
    assert "answer_json" not in body["puzzle"]
    assert {easy.id, mid.id, hard.id}  # fixtures exist


def test_cold_start_without_content_recommends_nothing(client, db_session):
    token = _token(client, "cold_empty")
    _ensure_exercise(db_session)
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["recommended_exercise"] is None
    assert res.json()["reason"] is None
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 404
    assert res.json()["detail"] == "no_eligible_content"


# --- candidate eligibility ----------------------------------------------------


def test_unpublished_and_retired_content_never_selected(client, db_session):
    token = _token(client, "elig_player")
    visible = _puzzle(db_session, rating=1200.0)
    _puzzle(db_session, rating=1200.0, published=False)  # draft
    retired = _puzzle(db_session, rating=1200.0)
    retired.is_archived = True
    retired.status = "retired"
    db_session.commit()
    for _ in range(3):
        res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
        assert res.status_code == 200, res.text
        assert res.json()["puzzle"]["id"] == visible.id


def test_flag_status_desync_never_selected(client, db_session):
    """Quarantined/rejected rows stay unservable even when the
    is_published/is_archived flags desync (lifecycle is authoritative)."""
    token = _token(client, "desync_player")
    visible = _puzzle(db_session, rating=1200.0)
    for bad_status in ("quarantined", "rejected"):
        bad = _puzzle(db_session, rating=1200.0)
        bad.status = bad_status
        bad.is_published = True
        bad.is_archived = False
        db_session.commit()
    for _ in range(3):
        res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
        assert res.status_code == 200, res.text
        assert res.json()["puzzle"]["id"] == visible.id


def test_disabled_exercise_yields_nothing(client, db_session):
    token = _token(client, "disabled_player")
    _puzzle(db_session, rating=1200.0)
    _ensure_exercise(db_session, active=False)
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 404
    assert res.json()["detail"] == "exercise_not_available"


def test_exercise_scope_is_strict(client, db_session):
    token = _token(client, "scope_player")
    own = _puzzle(db_session, slug=SLUG, rating=1200.0)
    _puzzle(db_session, slug=OTHER_SLUG, rating=1200.0)
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["puzzle"]["id"] == own.id
    assert res.json()["puzzle"]["exercise_slug"] == SLUG


def test_unknown_exercise_404(client, db_session):
    token = _token(client, "unknown_ex")
    res = client.get("/api/v1/me/adaptive/next?exercise=nope-slug", headers=_bearer(token))
    assert res.status_code == 404
    assert res.json()["detail"] == "exercise_not_found"


# --- difficulty matching ------------------------------------------------------


def test_suitable_difficulty_preferred_over_extremes(client, db_session):
    token = _token(client, "diff_player")
    _puzzle(db_session, rating=400.0)
    suitable = _puzzle(db_session, rating=1250.0)
    _puzzle(db_session, rating=2900.0)
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["puzzle"]["id"] == suitable.id


def test_remediation_aims_below_ability(client, db_session):
    token = _token(client, "remed_player")
    low = _puzzle(db_session, rating=900.0)
    _puzzle(db_session, rating=1150.0)
    # Recent failures trigger RECENT_FAILURES (remediation): 5 attempts
    # with 4 non-correct in the recent window.
    for i in range(5):
        answer = _correct(low) if i == 2 else _wrong()
        res = _submit(client, token, low.id, answer)
        assert res.status_code == 200, res.text
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["reason"] == "RECENT_FAILURES"
    row = [e for e in res.json()["exercises"] if e["exercise"] == SLUG][0]
    assert row["repeated_mistakes"] >= 1
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reason"] == "RECENT_FAILURES"
    assert body["target_rating"] == 1000.0  # default ability 1200 - 200


def test_strong_performance_aims_slightly_above(client, db_session):
    token = _token(client, "strong_player")
    p1 = _puzzle(db_session, rating=1100.0)
    p2 = _puzzle(db_session, rating=1150.0)
    p3 = _puzzle(db_session, rating=1200.0)
    _puzzle(db_session, rating=1400.0)
    for puzzle in (p1, p2, p3, p1, p2):
        res = _submit(client, token, puzzle.id, _correct(puzzle), mode="rated")
        assert res.status_code == 200, res.text
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["reason"] == "READY_FOR_HARDER"
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    body = res.json()
    assert body["reason"] == "READY_FOR_HARDER"
    assert body["target_rating"] > body["ability_rating"]
    assert body["target_rating"] - body["ability_rating"] <= 300


def test_insufficient_observed_data_reported(client, db_session):
    token = _token(client, "obs_player")
    _puzzle(db_session, rating=1200.0)
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["observed_difficulty"] == "insufficient_data"


def test_observed_difficulty_flows_into_selection(client, db_session):
    owner = _token(client, "obs_owner")
    puzzle = _puzzle(db_session, rating=1200.0)
    # Five correct attempts from another learner => observed easy.
    for i in range(5):
        helper = _token(client, f"obs_helper_{i}")
        res = _submit(client, helper, puzzle.id, _correct(puzzle))
        assert res.status_code == 200, res.text
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(owner))
    assert res.status_code == 200, res.text
    assert res.json()["observed_difficulty"] == "easy"


# --- performance signals ------------------------------------------------------


def test_weak_exercise_detected_from_accuracy(client, db_session):
    token = _token(client, "weak_player")
    puzzle = _puzzle(db_session, rating=1200.0)
    other = _puzzle(db_session, rating=1200.0)
    # Old failures keep overall accuracy low while the recent window is
    # clean, so WEAK_EXERCISE (not RECENT_FAILURES) applies.
    for _ in range(12):
        assert _submit(client, token, puzzle.id, _wrong()).status_code == 200
    for _ in range(11):
        assert _submit(client, token, other.id, _correct(other)).status_code == 200
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    row = [e for e in res.json()["exercises"] if e["exercise"] == SLUG][0]
    assert row["attempts"] == 23
    assert row["accuracy"] < 0.5
    assert row["recent_failures"] < 3
    assert row["reason"] == "WEAK_EXERCISE"


def test_response_time_exposed_as_signal(client, db_session):
    token = _token(client, "slow_player")
    puzzle = _puzzle(db_session, rating=1200.0)
    assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    row = [e for e in res.json()["exercises"] if e["exercise"] == SLUG][0]
    assert row["avg_response_ms"] is None or row["avg_response_ms"] >= 0


def test_stale_strong_exercise_requests_mastery_review(client, db_session):
    from datetime import datetime, timedelta, timezone

    token = _token(client, "mastery_player")
    user_id = _user_id(client, token)
    puzzle = _puzzle(db_session, rating=1200.0)
    for _ in range(5):
        assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200
    stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    db_session.query(Attempt).filter(Attempt.user_id == user_id).update({"created_at": stale})
    db_session.commit()
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    row = [e for e in res.json()["exercises"] if e["exercise"] == SLUG][0]
    assert row["reason"] == "MASTERY_REVIEW"


def test_stale_weak_exercise_requests_reengagement(client, db_session):
    from datetime import datetime, timedelta, timezone

    token = _token(client, "stale_player")
    user_id = _user_id(client, token)
    puzzle = _puzzle(db_session, rating=1200.0)
    assert _submit(client, token, puzzle.id, _correct(puzzle)).status_code == 200
    assert _submit(client, token, puzzle.id, _wrong()).status_code == 200
    stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    db_session.query(Attempt).filter(Attempt.user_id == user_id).update({"created_at": stale})
    db_session.commit()
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["reason"] == "LOW_RECENT_ACTIVITY"


# --- history / repetition -----------------------------------------------------


def test_recently_attempted_content_avoided(client, db_session):
    token = _token(client, "repeat_player")
    seen = _puzzle(db_session, rating=1200.0)
    fresh = _puzzle(db_session, rating=1200.0)
    assert _submit(client, token, seen.id, _correct(seen)).status_code == 200
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert res.json()["puzzle"]["id"] == fresh.id
    assert res.json()["fallback"] is False


def test_fallback_relaxes_recency_when_everything_seen(client, db_session):
    token = _token(client, "fallback_player")
    only = _puzzle(db_session, rating=1200.0)
    assert _submit(client, token, only.id, _correct(only)).status_code == 200
    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["puzzle"]["id"] == only.id
    assert body["fallback"] is True


# --- determinism --------------------------------------------------------------


def test_selection_deterministic_without_seed(client, db_session):
    token = _token(client, "determ_player")
    for rating in (1100.0, 1150.0, 1300.0):
        _puzzle(db_session, rating=rating)
    first = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token)).json()
    second = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token)).json()
    assert first["puzzle"]["id"] == second["puzzle"]["id"]
    assert first["reason"] == second["reason"]


def test_fixed_seed_reproducible_and_seed_free_of_global_random(client, db_session):
    token = _token(client, "seed_player")
    for rating in (1100.0, 1150.0, 1200.0, 1250.0, 1300.0, 1350.0):
        _puzzle(db_session, rating=rating)
    random.seed(12345)
    first = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}&seed=7", headers=_bearer(token)).json()
    random.seed(99999)  # global state must not affect selection
    second = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}&seed=7", headers=_bearer(token)).json()
    assert first["puzzle"]["id"] == second["puzzle"]["id"]


def test_pure_ranking_stable_and_seeded_choice_reproducible(db_session):
    _ensure_exercise(db_session)
    puzzles = [_puzzle(db_session, rating=r) for r in (1000.0, 1100.0, 1300.0)]
    ranked = adaptive.rank_candidates(puzzles, target=1120.0)
    assert [c.puzzle_id for c in ranked] == [puzzles[1].id, puzzles[0].id, puzzles[2].id]
    first = adaptive.pick_candidate(ranked, seed=42)
    second = adaptive.pick_candidate(ranked, seed=42, rng=random.Random(42))
    assert first is not None and second is not None
    assert first.puzzle_id == second.puzzle_id


# --- outcomes -----------------------------------------------------------------


def test_outcome_lifecycle_and_history(client, db_session):
    token = _token(client, "outcome_player")
    _puzzle(db_session, rating=1200.0)
    nxt = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token)).json()
    rec_id = nxt["recommendation_id"]
    # Invalid: shown -> completed skips accepted.
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "completed"},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "accepted"},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "accepted"
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "completed", "result": "correct"},
        headers=_bearer(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "completed"
    assert res.json()["result"] == "correct"
    # Terminal states never reopen.
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "skipped"},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    res = client.get("/api/v1/me/adaptive/history", headers=_bearer(token))
    assert res.status_code == 200, res.text
    assert any(row["id"] == rec_id and row["status"] == "completed" for row in res.json())


def test_outcome_invalid_status_and_result_rejected(client, db_session):
    token = _token(client, "outcome_bad")
    _puzzle(db_session, rating=1200.0)
    rec_id = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token)).json()[
        "recommendation_id"
    ]
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "teleported"},
        headers=_bearer(token),
    )
    assert res.status_code == 422
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "accepted", "result": "teleported"},
        headers=_bearer(token),
    )
    assert res.status_code == 422


def test_outcome_foreign_recommendation_404(client, db_session):
    token_a = _token(client, "outcome_owner")
    token_b = _token(client, "outcome_other")
    _puzzle(db_session, rating=1200.0)
    rec_id = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token_a)).json()[
        "recommendation_id"
    ]
    res = client.post(
        f"/api/v1/me/adaptive/outcomes/{rec_id}",
        json={"status": "skipped"},
        headers=_bearer(token_b),
    )
    assert res.status_code == 404


# --- security -----------------------------------------------------------------


def test_anonymous_adaptive_access_denied(client, db_session):
    _puzzle(db_session, rating=1200.0)
    assert client.get("/api/v1/me/adaptive/overview").status_code == 401
    assert client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}").status_code == 401
    assert client.get("/api/v1/me/adaptive/history").status_code == 401


def test_cross_user_adaptive_isolation(client, db_session):
    token_a = _token(client, "iso_a")
    token_b = _token(client, "iso_b")
    _puzzle(db_session, rating=1200.0)
    rec_id = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token_a)).json()[
        "recommendation_id"
    ]
    res = client.get("/api/v1/me/adaptive/history", headers=_bearer(token_b))
    assert res.status_code == 200
    assert all(row["id"] != rec_id for row in res.json())


def _invite(client, db_session, mentor, student, kind):
    mentor_token = _token(client, mentor)
    student_token = _token(client, student)
    _grant(db_session, mentor, "COACH" if kind == "coach" else "PARENT")
    res = client.post(
        "/api/v1/relationships",
        json={"kind": kind, "other_username": student},
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 201, res.text
    return mentor_token, student_token, res.json()["id"]


def _activate(client, mentor_token, student_token, rel_id):
    res = client.post(f"/api/v1/relationships/{rel_id}/accept", headers=_bearer(student_token))
    assert res.status_code == 200, res.text


def test_coach_authorized_student_adaptive_overview(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_x", "learner_x", "coach")
    student_id = _user_id(client, student_token)
    puzzle = _puzzle(db_session, rating=1200.0)
    assert _submit(client, student_token, puzzle.id, _wrong()).status_code == 200
    _activate(client, mentor_token, student_token, rel_id)
    res = client.get(
        f"/api/v1/coach/students/{student_id}/adaptive/overview", headers=_bearer(mentor_token)
    )
    assert res.status_code == 200, res.text
    assert any(e["exercise"] == SLUG for e in res.json()["exercises"])
    res = client.get(
        f"/api/v1/coach/students/{student_id}/adaptive/exercises/{SLUG}",
        headers=_bearer(mentor_token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["exercise"] == SLUG
    assert "answer_json" not in res.text


def test_coach_unrelated_student_denied(client, db_session):
    mentor_token, _, rel_id = _invite(client, db_session, "coach_y", "learner_y", "coach")
    stranger_token = _token(client, "stranger_y")
    stranger_id = _user_id(client, stranger_token)
    _puzzle(db_session, rating=1200.0)
    res = client.get(
        f"/api/v1/coach/students/{stranger_id}/adaptive/overview", headers=_bearer(mentor_token)
    )
    assert res.status_code == 404
    _ = rel_id


def test_parent_authorized_child_adaptive_overview(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "parent_x", "child_x", "parent")
    student_id = _user_id(client, student_token)
    _puzzle(db_session, rating=1200.0)
    _activate(client, mentor_token, student_token, rel_id)
    res = client.get(
        f"/api/v1/parent/children/{student_id}/adaptive/overview", headers=_bearer(mentor_token)
    )
    assert res.status_code == 200, res.text
    assert res.json()["reason"] == "COLD_START"


def test_parent_unrelated_child_denied_and_kind_separation(client, db_session):
    coach_token, student_token, rel_id = _invite(client, db_session, "coach_z", "learner_z", "coach")
    student_id = _user_id(client, student_token)
    _activate(client, coach_token, student_token, rel_id)
    # A coach edge never authorizes parent endpoints and vice versa.
    res = client.get(
        f"/api/v1/parent/children/{student_id}/adaptive/overview", headers=_bearer(coach_token)
    )
    assert res.status_code == 404
    parent_token, _, parent_rel = _invite(client, db_session, "parent_z", "child_z", "parent")
    res = client.get(
        f"/api/v1/coach/students/{student_id}/adaptive/overview", headers=_bearer(parent_token)
    )
    assert res.status_code == 404
    _ = parent_rel


def test_revoked_relationship_blocks_adaptive_access(client, db_session):
    mentor_token, student_token, rel_id = _invite(client, db_session, "coach_r", "learner_r", "coach")
    student_id = _user_id(client, student_token)
    _puzzle(db_session, rating=1200.0)
    _activate(client, mentor_token, student_token, rel_id)
    res = client.get(
        f"/api/v1/coach/students/{student_id}/adaptive/overview", headers=_bearer(mentor_token)
    )
    assert res.status_code == 200
    res = client.post(f"/api/v1/relationships/{rel_id}/revoke", headers=_bearer(mentor_token))
    assert res.status_code == 200, res.text
    res = client.get(
        f"/api/v1/coach/students/{student_id}/adaptive/overview", headers=_bearer(mentor_token)
    )
    assert res.status_code == 404


# --- invariants: selection mutates nothing authoritative ----------------------


def test_adaptive_selection_mutates_no_training_state(client, db_session):
    token = _token(client, "invariant_player")
    user_id = _user_id(client, token)
    puzzle = _puzzle(db_session, rating=1200.0)
    assert _submit(client, token, puzzle.id, _correct(puzzle), mode="rated").status_code == 200

    def _counts():
        return (
            db_session.query(Attempt).count(),
            db_session.query(RatingEvent).count(),
            db_session.query(XpEvent).count(),
            db_session.query(AdaptiveRecommendation).count(),
        )

    attempts_before, ratings_before, xp_before, recs_before = _counts()
    rating_before = db_session.query(PlayerRating).filter(PlayerRating.user_id == user_id).one().rating
    xp_total_before = db_session.query(PlayerGamificationState).filter(
        PlayerGamificationState.user_id == user_id
    ).one().total_xp
    puzzle_rating_before = db_session.get(Puzzle, puzzle.id).initial_rating

    res = client.get(f"/api/v1/me/adaptive/next?exercise={SLUG}", headers=_bearer(token))
    assert res.status_code == 200, res.text
    res = client.get("/api/v1/me/adaptive/overview", headers=_bearer(token))
    assert res.status_code == 200, res.text

    attempts_after, ratings_after, xp_after, recs_after = _counts()
    assert (attempts_after, ratings_after, xp_after) == (attempts_before, ratings_before, xp_before)
    assert recs_after == recs_before + 1  # only the owned recommendation row
    assert (
        db_session.query(PlayerRating).filter(PlayerRating.user_id == user_id).one().rating
        == rating_before
    )
    assert (
        db_session.query(PlayerGamificationState).filter(PlayerGamificationState.user_id == user_id).one().total_xp
        == xp_total_before
    )
    assert db_session.get(Puzzle, puzzle.id).initial_rating == puzzle_rating_before
    assert db_session.get(Puzzle, puzzle.id).status == "published"


# --- migration ------------------------------------------------------------------


def test_fresh_database_boots_to_v9_with_adaptive_table():
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version

    assert SCHEMA_VERSION == 16
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert ensure_schema(engine) == SCHEMA_VERSION
    assert get_schema_version(engine) == SCHEMA_VERSION
    assert "adaptive_recommendations" in inspect(engine).get_table_names()
    assert "adaptive_recommendations" in Base.metadata.tables
    assert ensure_schema(engine) == SCHEMA_VERSION  # idempotent re-run
