"""Balance Scale: values, validation, seed, API."""

import pytest

from app.modules.balance_scale import seed as seed_mod
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
from app.modules.rule_engine.base import AttemptResult


def answer_for(bank: list, right: list) -> dict:
    return {"bank": bank, "right": right}


def attempt(pieces: object) -> dict:
    return {"pieces": pieces}


# --- Value calculation ---


def test_piece_values():
    assert VALUES == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
    assert total_value(["Q", "R", "P"]) == 15
    assert total_value([]) == 0


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


# --- Validation ---


def test_exact_balance_is_correct():
    out = validate(answer_for(["R", "P"], ["B", "B"]), attempt(["R", "P"]))
    assert out.result == AttemptResult.CORRECT
    assert out.detail["submitted_value"] == 6
    assert out.detail["target_value"] == 6


def test_imbalance_is_wrong():
    out = validate(answer_for(["Q", "R", "B", "N", "P", "P"], ["Q"]), attempt(["B", "P", "P"]))
    assert out.result == AttemptResult.WRONG
    assert out.detail["submitted_value"] == 5
    assert out.detail["target_value"] == 9


def test_multiple_valid_combinations_accepted():
    answer = answer_for(["B", "P", "N"], ["P", "P", "P", "P"])
    assert validate(answer, attempt(["B", "P"])).result == AttemptResult.CORRECT
    assert validate(answer, attempt(["N", "P"])).result == AttemptResult.CORRECT


def test_order_does_not_matter():
    answer = answer_for(["R", "P"], ["B", "B"])
    assert validate(answer, attempt(["P", "R"])).result == AttemptResult.CORRECT


def test_duplicates_allowed_within_bank():
    answer = answer_for(["P", "P", "P", "R"], ["P", "P"])
    assert validate(answer, attempt(["P", "P"])).result == AttemptResult.CORRECT


def test_too_many_copies_rejected():
    answer = answer_for(["P", "P", "P", "R"], ["P", "P"])
    out = validate(answer, attempt(["P", "P", "P", "P"]))
    assert out.result == AttemptResult.WRONG


def test_piece_not_in_bank_rejected():
    answer = answer_for(["R", "P"], ["B", "B"])
    assert validate(answer, attempt(["Q", "Q"])).result == AttemptResult.WRONG
    assert validate(answer, attempt(["R", "R"])).result == AttemptResult.WRONG


def test_malformed_answer_safe():
    answer = answer_for(["R", "P"], ["B", "B"])
    assert validate(answer, {}).result == AttemptResult.WRONG
    assert validate(answer, {"pieces": "R"}).result == AttemptResult.WRONG
    assert validate(answer, {"pieces": None}).result == AttemptResult.WRONG
    assert validate(answer, {"pieces": ["R", "K"]}).result == AttemptResult.WRONG
    assert validate(answer, {"pieces": ["R", 5]}).result == AttemptResult.WRONG
    assert validate(answer, {"pieces": ["R", ""]} ).result == AttemptResult.WRONG
    assert validate(answer, None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_empty_answer_when_target_positive_is_wrong():
    assert validate(answer_for(["P"], ["P"]), attempt([])).result == AttemptResult.WRONG


def test_no_chess_legality_assumptions():
    # Color/case are irrelevant; lowercase bank works the same.
    answer = answer_for(["r", "p"], ["b", "b"])
    assert validate(answer, attempt(["R", "P"])).result == AttemptResult.CORRECT


def test_client_cannot_force_correctness():
    answer = answer_for(["R"], ["B", "B"])
    out = validate(answer, {"pieces": ["P"], "result": "correct", "target_value": 6})
    assert out.result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


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
        bank = puzzle.position_json["bank"]
        right = puzzle.position_json["right"]
        assert puzzle.answer_json == {"bank": bank, "right": right}
        assert all(normalize_piece(p) is not None for p in bank + right)
        target = total_value(right)
        assert target > 0
        assert seed_mod.reachable(bank, target) is True
        ratings.add(puzzle.initial_rating)
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len(ratings) >= 5


def test_seed_rejects_broken_puzzles():
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"bank": ["K"], "right": ["P"]})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"bank": ["P"], "right": ["Q"]})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"bank": [], "right": ["P"]})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"bank": ["R"], "right": []})


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
    assert body[0]["position_json"]["bank"]
    assert body[0]["position_json"]["right"]
    assert body[0]["fen"] is None
    assert puzzle.id > 0


def test_api_submit_correct_and_wrong(client, db_session):
    puzzle = _seeded(db_session)
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": ["P"]}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": ["N"]}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": ["P"]}, "mode": "rated"},
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
