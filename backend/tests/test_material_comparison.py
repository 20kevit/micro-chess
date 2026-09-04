"""Material Comparison: values, validation, seed, API."""

import pytest

from app.modules.exercises import registry
from app.modules.material_comparison import seed as seed_mod
from app.modules.material_comparison.validator import (
    SLUG,
    VALUES,
    expected_choice,
    normalize_choice,
    normalize_piece,
    total_value,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(left: object, right: object) -> dict:
    return {"left": left, "right": right}


def attempt(choice: object) -> dict:
    return {"choice": choice}


# --- Value calculation ---


def test_piece_values():
    assert VALUES == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
    assert total_value(["Q", "B"]) == 12
    assert total_value([]) == 0


def test_king_rejected():
    assert normalize_piece("K") is None
    assert normalize_piece("k") is None
    assert normalize_piece("X") is None
    assert normalize_piece("") is None
    assert normalize_piece(None) is None
    assert normalize_piece(9) is None


def test_normalize_case_insensitive():
    assert normalize_piece(" q ") == "Q"
    assert normalize_piece("n") == "N"


# --- Result calculation ---


def test_expected_choice():
    assert expected_choice(8, 5) == "left"
    assert expected_choice(7, 10) == "right"
    assert expected_choice(8, 8) == "equal"


# --- Validation ---


def test_correct_left_right_equal():
    assert validate(answer_for(["R"], ["P"]), attempt("left")).result == AttemptResult.CORRECT
    assert validate(answer_for(["P"], ["R"]), attempt("right")).result == AttemptResult.CORRECT
    assert validate(answer_for(["Q"], ["R", "B", "P"]), attempt("equal")).result == AttemptResult.CORRECT


def test_wrong_answer():
    out = validate(answer_for(["R"], ["P"]), attempt("right"))
    assert out.result == AttemptResult.WRONG
    assert out.detail["left_value"] == 5
    assert out.detail["right_value"] == 1
    assert out.detail["wrong"] == ["right"]


def test_malformed_answer_safe():
    answer = answer_for(["R"], ["P"])
    assert validate(answer, {}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": "up"}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": ""}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": None}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": 42}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": ["left"]}).result == AttemptResult.WRONG
    assert validate(answer, None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_unsupported_choice_rejected():
    assert validate(answer_for(["Q"], ["Q"]), attempt("draw")).result == AttemptResult.WRONG


def test_fake_client_totals_ignored():
    answer = answer_for(["R"], ["P"])
    out = validate(answer, {"choice": "left", "left_value": 100, "right_value": 1})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["left_value"] == 5
    assert out.detail["right_value"] == 1


def test_extra_fields_do_not_matter():
    answer = answer_for(["R"], ["P"])
    assert validate(answer, {"choice": "left", "foo": "bar"}).result == AttemptResult.CORRECT
    assert validate(answer, {"choice": "LEFT"}).result == AttemptResult.CORRECT


def test_colors_irrelevant_and_duplicates_count():
    answer = answer_for(["r", "p"], ["b", "b"])
    assert validate(answer, attempt("equal")).result == AttemptResult.CORRECT
    assert validate(answer_for(["P", "P"], ["N", "N"]), attempt("right")).result == AttemptResult.CORRECT


def test_client_cannot_force_correctness():
    answer = answer_for(["P"], ["R"])
    out = validate(answer, {"choice": "left", "result": "correct", "score": 1.0})
    assert out.result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed ---


def test_seed_is_deterministic_and_idempotent(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15


def test_seed_puzzles_valid_with_sensible_distribution(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    distribution: dict[str, int] = {}
    ratings = set()
    for puzzle in puzzles:
        assert puzzle.fen is None  # no board for this exercise
        left = puzzle.position_json["left"]
        right = puzzle.position_json["right"]
        assert puzzle.answer_json == {"left": left, "right": right}
        assert all(normalize_piece(p) is not None for p in left + right)
        # Independent total calculation (no shared helpers with seed verify).
        left_value = sum({"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}[p] for p in left)
        right_value = sum({"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}[p] for p in right)
        expected = "left" if left_value > right_value else "right" if right_value > left_value else "equal"
        distribution[expected] = distribution.get(expected, 0) + 1
        # ...and the validator agrees with the independent recomputation:
        assert validate(puzzle.answer_json, {"choice": expected}).result == AttemptResult.CORRECT
        ratings.add(puzzle.initial_rating)
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert distribution.get("equal", 0) == 3
    assert distribution.get("left", 0) >= 5
    assert distribution.get("right", 0) >= 5
    assert len(ratings) >= 5


def test_seed_rejects_broken_puzzles():
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"left": ["K"], "right": ["P"]})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"left": [], "right": ["P"]})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"left": ["Q"], "right": "Q"})


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
    assert body[0]["position_json"]["right"]
    assert body[0]["fen"] is None
    assert puzzle.id > 0


def test_api_submit_correct_and_wrong(client, db_session):
    puzzle = _seeded(db_session)
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": "left"}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": "equal"}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": "left"}, "mode": "rated"},
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
