"""Balance Scale (Exercise 10): values, solver, validation, scoring, generator, sessions, API."""

import random

import pytest

from app.modules.balance_scale import generator as gen_mod
from app.modules.balance_scale import seed as seed_mod
from app.modules.balance_scale import sessions as sess_mod
from app.modules.balance_scale.scoring import score_balance
from app.modules.balance_scale.solver import MAX_PIECES, optimal_combination, optimal_count
from app.modules.balance_scale.validator import (
    SLUG,
    VALUES,
    counts,
    normalize_piece,
    total_value,
    validate,
)
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult, ValidationResult


def answer_for(left: list) -> dict:
    return {"left": left}


def attempt(pieces: object) -> dict:
    return {"pieces": pieces}


# --- Value calculation ---


def test_piece_values():
    assert VALUES == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
    assert total_value(["Q", "R", "P"]) == 15
    assert total_value([]) == 0


def test_target_calculation():
    assert total_value(["Q", "Q", "R", "B", "P"]) == 9 + 9 + 5 + 3 + 1
    assert total_value(["N", "N", "P", "P", "P", "P"]) == 10


def test_king_is_invalid():
    assert normalize_piece("K") is None
    assert normalize_piece("k") is None
    assert normalize_piece("X") is None
    assert normalize_piece("") is None
    assert normalize_piece(None) is None
    assert normalize_piece(5) is None


def test_normalize_is_case_insensitive():
    assert normalize_piece(" q ") == "Q"
    assert normalize_piece("n") == "N"


def test_counts_handle_duplicates():
    assert counts(["P", "P", "R"]) == {"P": 2, "R": 1}


# --- Optimal solver ---


@pytest.mark.parametrize(
    "target,expected",
    [
        (1, 1),
        (3, 1),
        (5, 1),
        (9, 1),
        (4, 2),
        (6, 2),
        (8, 2),
        (10, 2),
        (18, 2),
        (17, 3),
        (90, 10),
    ],
)
def test_optimal_solver(target, expected):
    assert optimal_count(target) == expected


def test_optimal_solver_rejects_non_positive():
    assert optimal_count(0) is None
    assert optimal_count(-4) is None


def test_optimal_combination_sums_to_target_and_is_minimal():
    for target in [4, 6, 8, 10, 17, 18, 31, 54, 90]:
        combo = optimal_combination(target)
        assert total_value([p.upper() for p in combo]) == target
        assert len(combo) == optimal_count(target)


def test_optimal_combination_rejects_bad_target():
    with pytest.raises(ValueError):
        optimal_combination(0)


# --- Validation: exact balance ---


def test_exact_balance_accepted():
    out = validate(answer_for(["q", "r", "b"]), attempt(["q", "r", "b"]))
    assert out.result == AttemptResult.CORRECT
    assert out.detail["submitted_value"] == 17
    assert out.detail["target_value"] == 17
    assert out.detail["used_count"] == 3
    assert out.detail["optimal_count"] == 3


def test_under_target_not_solved():
    out = validate(answer_for(["q", "r", "b"]), attempt(["q", "r"]))
    assert out.result == AttemptResult.WRONG


def test_over_target_not_solved():
    out = validate(answer_for(["q", "r", "b"]), attempt(["q", "q"]))
    assert out.result == AttemptResult.WRONG


def test_invalid_piece_rejected():
    assert validate(answer_for(["q", "r", "b", "p"]), attempt(["q", "k"])).result == AttemptResult.WRONG
    assert validate(answer_for(["q", "r", "b", "p"]), attempt(["q", 5])).result == AttemptResult.WRONG


def test_more_than_10_pieces_rejected():
    left = ["q"] * 10  # target 90
    out = validate(answer_for(left), attempt(["p"] * 11))
    assert out.result == AttemptResult.WRONG


def test_10_queens_match_90():
    out = validate(answer_for(["q"] * 10), attempt(["q"] * 10))
    assert out.result == AttemptResult.CORRECT
    assert out.detail["used_count"] == 10
    assert out.detail["optimal_count"] == 10


def test_malformed_input_safe():
    assert validate(answer_for(["q", "r", "b", "p"]), {}).result == AttemptResult.WRONG
    assert validate(answer_for(["q", "r", "b", "p"]), {"pieces": "Q"}).result == AttemptResult.WRONG
    assert validate(answer_for(["q", "r", "b", "p"]), {"pieces": None}).result == AttemptResult.WRONG
    assert validate(None, attempt(["q"])).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(attempt(["q"]), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_client_cannot_force_correctness():
    out = validate(
        answer_for(["q", "r", "b", "p"]),
        {"pieces": ["p"], "result": "correct", "score": 10, "optimal_count": 1, "target_value": 1},
    )
    assert out.result == AttemptResult.WRONG


def test_client_target_optimal_score_ignored():
    # Stored target is 17; client claims target 5 / optimal 1 / score 10.
    out = validate(
        answer_for(["q", "r", "b"]),
        {"pieces": ["q", "r", "b"], "target_value": 5, "optimal_count": 1, "score": 10},
    )
    assert out.result == AttemptResult.CORRECT
    assert out.detail["target_value"] == 17
    assert out.detail["optimal_count"] == 3


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Scoring ---


def _correct_validation(used: int, optimal: int) -> ValidationResult:
    return ValidationResult(
        result=AttemptResult.CORRECT,
        message_key="feedback.correct",
        detail={"used_count": used, "optimal_count": optimal},
    )


def test_scoring_optimal_is_10():
    assert score_balance(_correct_validation(3, 3)) == 10.0


def test_scoring_extra_pieces():
    assert score_balance(_correct_validation(4, 3)) == 9.0
    assert score_balance(_correct_validation(5, 3)) == 8.0
    assert score_balance(_correct_validation(6, 3)) == 7.0


def test_scoring_floor_is_zero():
    assert score_balance(_correct_validation(13, 3)) == 0.0
    assert score_balance(_correct_validation(25, 3)) == 0.0


def test_scoring_wrong_is_zero():
    wrong = ValidationResult(result=AttemptResult.WRONG, message_key="feedback.wrong", detail={})
    assert score_balance(wrong) == 0.0


def test_scoring_example_target_17():
    # Optimal 9+5+3 (3 pieces) scores 10; 5-piece solutions score 8.
    assert score_balance(_correct_validation(3, 3)) == 10.0
    assert score_balance(_correct_validation(5, 3)) == 8.0


# --- Multiple optimal solutions ---


def test_multiple_optimal_solutions_all_accepted():
    # Target 10: 9+1 and 5+5 are both 2-piece optimals.
    answer = answer_for(["r", "r", "p", "p", "n", "n"])  # 5+5+1+1+3+3 = 18? no -> use seed-like 10
    answer10 = answer_for(["n", "n", "p", "p", "p", "p"])  # 3+3+1+1+1+1 = 10
    assert validate(answer10, attempt(["q", "p"])).result == AttemptResult.CORRECT
    assert validate(answer10, attempt(["r", "r"])).result == AttemptResult.CORRECT
    assert validate(answer10, attempt(["n", "n", "p", "p", "p", "p"])).result == AttemptResult.CORRECT
    assert answer is not None  # silence lint about unused helper path


def test_non_minimal_exact_still_solves_with_fewer_points():
    out = validate(answer_for(["q", "r", "b"]), attempt(["r", "r", "r", "p", "p"]))
    assert out.result == AttemptResult.CORRECT
    assert score_balance(
        ValidationResult(result=out.result, message_key=out.message_key, detail=out.detail)
    ) == 8.0


# --- Generator ---


def test_generator_shape_and_solvability():
    rng = random.Random(42)
    seen_targets: set[int] = set()
    seen_optimals: set[int] = set()
    for _ in range(60):
        data = gen_mod.generate_question_data(rng)
        left = data["left"]
        assert 4 <= len(left) <= 10
        assert all(normalize_piece(p) is not None for p in left)
        assert data["target"] == total_value([p.upper() for p in left])
        assert data["optimal_count"] == optimal_count(data["target"])
        assert data["optimal_count"] <= MAX_PIECES
        assert optimal_combination(data["target"]) is not None
        seen_targets.add(data["target"])
        seen_optimals.add(data["optimal_count"])
    # Distribution sanity: not pathological — several distinct targets
    # and optimal sizes across the sample.
    assert len(seen_targets) >= 8
    assert len(seen_optimals) >= 3


def test_generator_no_impossible_target():
    rng = random.Random(7)
    for _ in range(100):
        data = gen_mod.generate_question_data(rng)
        assert data["optimal_count"] <= MAX_PIECES


def test_generator_not_only_trivial():
    rng = random.Random(1234)
    optimals = [gen_mod.generate_question_data(rng)["optimal_count"] for _ in range(50)]
    assert any(o > 1 for o in optimals)
    assert sum(1 for o in optimals if o == 1) < 40


# --- Seed ---


def test_seed_is_deterministic_and_idempotent(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15


def test_seed_puzzles_valid_and_solvable(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    ratings = set()
    for puzzle in puzzles:
        assert puzzle.fen is None  # no board for this exercise
        left = puzzle.position_json["left"]
        assert puzzle.answer_json["left"] == left
        target, optimal = seed_mod.verify_left(left)
        assert puzzle.answer_json["target"] == target
        assert puzzle.answer_json["optimal_count"] == optimal
        # position_json must NOT leak the optimal count.
        assert "optimal_count" not in puzzle.position_json
        assert "target" not in puzzle.position_json
        ratings.add(puzzle.initial_rating)
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len(ratings) >= 5


def test_seed_rejects_broken_puzzles():
    with pytest.raises(ValueError):
        seed_mod.verify_left(["k", "p", "p", "p"])
    with pytest.raises(ValueError):
        seed_mod.verify_left(["p", "p", "p"])  # too few
    with pytest.raises(ValueError):
        seed_mod.verify_left(["p"] * 11)  # too many


# --- API ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_api_list_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    assert body[0]["position_json"]["left"]
    assert "optimal_count" not in body[0]["position_json"]
    assert body[0]["fen"] is None
    assert puzzle.id > 0


def test_api_next_practice_puzzle_hides_answer(client, db_session):
    res = client.post("/api/v1/balance-scale/next", json={"exclude_ids": []})
    assert res.status_code == 200
    body = res.json()
    assert body["position_json"]["left"]
    assert "answer_json" not in body
    assert "optimal_count" not in body["position_json"]


def test_api_submit_correct_scores_by_count(client, db_session):
    puzzle = _seeded(db_session)
    left = puzzle.position_json["left"]
    target = total_value([p.upper() for p in left])
    combo = optimal_combination(target)
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": combo}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 10.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": ["p"]}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"
    assert bad.json()["score"] == 0.0

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": combo}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_api_invalid_puzzle_id_404(client, db_session):
    res = client.get("/api/v1/puzzles/999999")
    assert res.status_code == 404


# --- Session lifecycle ---


def test_speed_session_lifecycle(client, db_session):
    opened = client.post("/api/v1/balance-scale/sessions", json={})
    assert opened.status_code == 200
    sid = opened.json()["session_id"]
    assert opened.json()["status"] == "preparing"

    # Cannot start without the 20-puzzle buffer.
    assert client.post(f"/api/v1/balance-scale/sessions/{sid}/start").status_code == 409

    # Cannot submit before the clock starts.
    assert (
        client.post(
            f"/api/v1/balance-scale/sessions/{sid}/submit",
            json={"puzzle_id": 1, "answer": {"pieces": ["p"]}},
        ).status_code
        == 409
    )

    prepared = client.post(f"/api/v1/balance-scale/sessions/{sid}/puzzles", json={"count": 20})
    assert prepared.status_code == 200
    assert len(prepared.json()) == 20
    for row in prepared.json():
        assert "answer_json" not in row

    started = client.post(f"/api/v1/balance-scale/sessions/{sid}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    puzzle_id = prepared.json()[0]["id"]
    puzzle = db_session.get(Puzzle, puzzle_id)
    assert puzzle is not None
    target = total_value([p.upper() for p in puzzle.position_json["left"]])
    combo = optimal_combination(target)
    # Client tries to smuggle score/optimal/target — all ignored.
    sub = client.post(
        f"/api/v1/balance-scale/sessions/{sid}/submit",
        json={
            "puzzle_id": puzzle_id,
            "answer": {"pieces": combo, "score": 99, "optimal_count": 1, "target_value": 1},
        },
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    assert sub.json()["attempt"]["score"] == 10.0

    nxt = client.post(f"/api/v1/balance-scale/sessions/{sid}/next")
    assert nxt.status_code == 200
    assert "answer_json" not in nxt.json()

    report = client.get(f"/api/v1/balance-scale/sessions/{sid}/report")
    assert report.status_code == 200
    assert report.json()["session"]["attempted"] == 1
    assert len(report.json()["entries"]) == 1

    finished = client.post(f"/api/v1/balance-scale/sessions/{sid}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"


def test_speed_session_rejects_foreign_puzzle(client, db_session):
    opened = client.post("/api/v1/balance-scale/sessions", json={})
    sid = opened.json()["session_id"]
    client.post(f"/api/v1/balance-scale/sessions/{sid}/puzzles", json={"count": 20})
    client.post(f"/api/v1/balance-scale/sessions/{sid}/start")
    res = client.post(
        f"/api/v1/balance-scale/sessions/{sid}/submit",
        json={"puzzle_id": 999999, "answer": {"pieces": ["p"]}},
    )
    assert res.status_code == 404


def test_speed_session_unknown_id_404(client, db_session):
    assert client.get("/api/v1/balance-scale/sessions/nope").status_code == 404


def test_speed_session_expiry(client, db_session):
    opened = client.post("/api/v1/balance-scale/sessions", json={})
    sid = opened.json()["session_id"]
    prepared = client.post(f"/api/v1/balance-scale/sessions/{sid}/puzzles", json={"count": 20})
    client.post(f"/api/v1/balance-scale/sessions/{sid}/start")
    session = sess_mod.get_session(db_session, sid)
    from datetime import datetime, timedelta, timezone

    session.ends_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()
    res = client.post(
        f"/api/v1/balance-scale/sessions/{sid}/submit",
        json={"puzzle_id": prepared.json()[0]["id"], "answer": {"pieces": ["p"]}},
    )
    assert res.status_code == 410
