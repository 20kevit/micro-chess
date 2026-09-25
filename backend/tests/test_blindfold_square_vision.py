"""Blindfold Square Vision: square colors, validation, scoring, seed, API."""

import random

import pytest

from app.modules.blindfold_square_vision import generator as gen_mod
from app.modules.blindfold_square_vision import seed as seed_mod
from app.modules.blindfold_square_vision.scoring import score_square_vision
from app.modules.blindfold_square_vision.validator import (
    SLUG,
    normalize_choice,
    square_color,
    validate,
)
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_generated_pool, publish_staged_puzzles


def answer_for(square: str) -> dict:
    return {"square": square}


# --- Deterministic square colors ---


def test_a1_is_dark_and_h1_is_light():
    assert square_color("a1") == "black"
    assert square_color("h1") == "white"
    assert square_color("a8") == "white"
    assert square_color("h8") == "black"


def test_adjacent_squares_alternate():
    files = "abcdefgh"
    for fi in range(8):
        for rank in range(1, 9):
            here = f"{files[fi]}{rank}"
            if fi < 7:
                assert square_color(f"{files[fi + 1]}{rank}") != square_color(here)
            if rank < 8:
                assert square_color(f"{files[fi]}{rank + 1}") != square_color(here)


def test_board_splits_evenly():
    files = "abcdefgh"
    colors = [square_color(f"{files[fi]}{rank}") for fi in range(8) for rank in range(1, 9)]
    assert len(colors) == 64
    assert colors.count("white") == 32
    assert colors.count("black") == 32


# --- Practice validation (tap the square) ---


def test_practice_correct_square():
    out = validate(answer_for("d5"), {"square": "d5"})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["correct"] == ["d5"]
    assert out.detail["missed"] == []
    assert out.detail["wrong"] == []


def test_practice_wrong_square_marks_tap_red_and_target_orange():
    out = validate(answer_for("d5"), {"square": "d4"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["wrong"] == ["d4"]
    assert out.detail["missed"] == ["d5"]
    assert out.detail["correct"] == []


def test_practice_malformed_square_safe():
    for bad in ("", "z9", "d5d5", None, 42, ["d5"]):
        out = validate(answer_for("d5"), {"square": bad})
        assert out.result == AttemptResult.WRONG


# --- Speed validation (name the color) ---


def test_speed_correct_and_wrong_choice():
    out = validate(answer_for("d5"), {"choice": "white"})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["correct"] == ["white"]
    bad = validate(answer_for("d5"), {"choice": "black"})
    assert bad.result == AttemptResult.WRONG
    assert bad.detail["wrong"] == ["black"]
    assert bad.detail["missed"] == ["white"]


def test_speed_malformed_choice_safe():
    for bad in ("green", "", None, 1, ["white"]):
        assert validate(answer_for("a1"), {"choice": bad}).result == AttemptResult.WRONG
    assert normalize_choice(" White ") == "white"


def test_client_color_never_overrides_server():
    # Even a "correct-looking" client payload loses to the stored square.
    out = validate(answer_for("a1"), {"choice": "white", "square": "h1"})
    assert out.result == AttemptResult.WRONG


def test_missing_target_fails_closed():
    assert validate({}, {"square": "d5"}).result == AttemptResult.WRONG
    assert validate({}, {"choice": "white"}).result == AttemptResult.WRONG


# --- Registry + scoring ---


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


def test_scoring_correct_plus5_wrong_minus3():
    assert score_square_vision(validate(answer_for("d5"), {"square": "d5"})) == 5.0
    assert score_square_vision(validate(answer_for("d5"), {"square": "d4"})) == -3.0
    assert score_square_vision(validate(answer_for("a1"), {"choice": "black"})) == 5.0
    assert score_square_vision(validate(answer_for("a1"), {"choice": "white"})) == -3.0


# --- Generator + seed ---


def test_generator_uniform_square_with_matching_prompt(db_session):
    puzzle = gen_mod.create_puzzle(db_session, random.Random(14))
    answer = puzzle.answer_json
    assert answer["square"] == puzzle.position_json["square"]
    assert answer["square"] in puzzle.prompt_fa
    assert puzzle.fen == gen_mod.EMPTY_FEN


def test_seed_covers_both_colors_and_is_idempotent(db_session):
    assert seed_mod.seed_db(db_session) == 8
    assert seed_mod.seed_db(db_session) == 0
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 8
    colors = {square_color(p.answer_json["square"]) for p in puzzles}
    assert colors == {"white", "black"}


# --- API ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


@pytest.fixture
def published_pool(db_session):
    seed_mod.seed_db(db_session)
    publish_generated_pool(db_session, SLUG, gen_mod.create_puzzle)


def test_api_next_hides_color(client, db_session, published_pool):
    res = client.post("/api/v1/blindfold-square-vision/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    assert len(body["position_json"]["square"]) == 2


def test_api_practice_submit_scores_plus5_minus3(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    target = puzzle.answer_json["square"]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"square": target}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 5.0

    wrong_square = "a1" if target != "a1" else "h8"
    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"square": wrong_square}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"
    assert bad.json()["score"] == -3.0


def test_speed_lifecycle(client, db_session, published_pool):
    started = client.post("/api/v1/blindfold-square-vision/sessions", json={})
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    buf = client.post(
        f"/api/v1/blindfold-square-vision/sessions/{session_id}/puzzles", json={"count": 20}
    )
    assert buf.status_code == 200
    assert len(buf.json()) == 20
    for entry in buf.json():
        assert "answer_json" not in entry
    clock = client.post(f"/api/v1/blindfold-square-vision/sessions/{session_id}/start")
    assert clock.status_code == 200
    first = buf.json()[0]
    expected = square_color(first["position_json"]["square"])
    sub = client.post(
        f"/api/v1/blindfold-square-vision/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"choice": expected}},
        headers=make_auth_headers(db_session),
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    assert sub.json()["attempt"]["score"] == 5.0
    report = client.get(f"/api/v1/blindfold-square-vision/sessions/{session_id}/report")
    assert report.status_code == 200
    assert report.json()["session"]["attempted"] == 1
    assert report.json()["session"]["score"] == 5.0
