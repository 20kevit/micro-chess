"""Heavier Side: material calculator, validator, generator, seed, API."""

import random

import pytest

from app.modules.exercises import registry
from app.modules.material_comparison import generator as gen_mod
from app.modules.material_comparison import material as mat
from app.modules.material_comparison import seed as seed_mod
from app.modules.material_comparison.scoring import score_heavier_side
from app.modules.material_comparison.validator import (
    SLUG,
    VALUES,
    expected_choice,
    normalize_choice,
    normalize_piece,
    total_value,
    validate,
)
from app.modules.puzzles.models import SOURCE_GENERATED, Puzzle
from app.modules.puzzles.service import stage_validated_puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_generated_pool, publish_staged_puzzles


def answer_for_fen(fen: str) -> dict:
    return {"fen": fen}


def attempt(choice: object) -> dict:
    return {"choice": choice}


# --- Material calculator ---


def test_piece_values():
    assert VALUES == {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9}
    assert total_value(["Q", "B"]) == 12
    assert total_value([]) == 0


def test_king_rejected_from_lists():
    assert normalize_piece("K") is None
    assert normalize_piece("k") is None
    assert normalize_piece("X") is None
    assert normalize_piece("") is None
    assert normalize_piece(None) is None
    assert normalize_piece(9) is None


def test_king_worth_zero_on_board():
    white, black = mat.material_from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert (white, black) == (0, 0)
    assert mat.classify(white, black) == "equal"


def test_startpos_equal_39():
    white, black = mat.material_from_fen(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    assert (white, black) == (39, 39)


def test_fen_queens_rooks_bishops_knights_pawns():
    # Queens only.
    assert mat.material_from_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1") == (9, 9)
    # Rook + pawns (10% boundary case).
    assert mat.material_from_fen("4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1") == (10, 9)
    # Knights only.
    assert mat.material_from_fen("4k3/8/8/4n3/4N3/8/8/4K3 w - - 0 1") == (3, 3)
    # Pawn endgame.
    assert mat.material_from_fen("8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1") == (3, 3)
    # Mixed middlegame.
    assert mat.material_from_fen(
        "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12"
    ) == (26, 24)


def test_material_agrees_with_python_chess():
    import chess

    fen = "r1bq1rk1/pp1n1ppp/2p1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQK2R w KQ - 0 1"
    board = chess.Board(fen)
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    white = sum(values[p.piece_type] for p in board.piece_map().values() if p.color == chess.WHITE)
    black = sum(values[p.piece_type] for p in board.piece_map().values() if p.color == chess.BLACK)
    assert mat.material_from_fen(fen) == (white, black)


def test_invalid_fen_raises():
    with pytest.raises(ValueError):
        mat.material_from_fen("not a fen")


# --- Classifier edge cases ---


def test_classifier_equal():
    assert mat.classify(20, 20) == "equal"
    assert mat.classify(0, 0) == "equal"
    assert expected_choice(8, 8) == "equal"


def test_classifier_white_ahead():
    assert mat.classify(30, 27) == "white"
    assert expected_choice(8, 5) == "white"


def test_classifier_black_ahead():
    assert mat.classify(27, 30) == "black"
    assert expected_choice(7, 10) == "black"


# --- Difficulty validator ---


def test_exactly_10_percent_accepted():
    assert mat.is_material_difference_acceptable(30, 27) is True
    assert mat.is_material_difference_acceptable(27, 30) is True
    assert mat.is_material_difference_acceptable(10, 9) is True


def test_above_10_percent_rejected():
    assert mat.is_material_difference_acceptable(30, 26) is False
    assert mat.is_material_difference_acceptable(26, 30) is False
    assert mat.is_material_difference_acceptable(30, 25) is False


def test_zero_zero_accepted():
    assert mat.is_material_difference_acceptable(0, 0) is True


def test_no_rounding_before_comparison():
    # 1/9 = 11.1% must be rejected even though it "rounds" to 11%.
    assert mat.is_material_difference_acceptable(9, 8) is False
    # 1/10 = exactly 10% accepted.
    assert mat.is_material_difference_acceptable(10, 9) is True
    # 1/11 = 9.09% accepted.
    assert mat.is_material_difference_acceptable(11, 10) is True


# --- FEN validator ---


def test_correct_white_black_equal():
    assert validate(answer_for_fen("4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1"), attempt("white")).result == AttemptResult.CORRECT
    assert validate(answer_for_fen("r3k3/3ppppp/8/8/8/8/4PPPP/4K1R1 w - - 0 1"), attempt("black")).result == AttemptResult.CORRECT
    assert validate(answer_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1"), attempt("equal")).result == AttemptResult.CORRECT


def test_wrong_answer_reports_expected():
    out = validate(answer_for_fen("4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1"), attempt("black"))
    assert out.result == AttemptResult.WRONG
    assert out.detail["wrong"] == ["black"]
    assert out.detail["missed"] == ["white"]


def test_malformed_answer_safe():
    answer = answer_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert validate(answer, {}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": "up"}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": ""}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": None}).result == AttemptResult.WRONG
    assert validate(answer, {"choice": 42}).result == AttemptResult.WRONG
    assert validate(answer, None).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate({}, attempt("white")).result == AttemptResult.WRONG
    assert validate({"fen": "bad fen"}, attempt("white")).result == AttemptResult.WRONG


def test_fake_client_totals_ignored():
    answer = answer_for_fen("4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1")
    out = validate(answer, {"choice": "white", "white_material": 100, "score": 99})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["white_material"] == 10
    assert out.detail["black_material"] == 9


def test_case_insensitive_choice():
    answer = answer_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert validate(answer, {"choice": "EQUAL"}).result == AttemptResult.CORRECT


def test_client_cannot_force_correctness():
    answer = answer_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    out = validate(answer, {"choice": "white", "result": "correct", "score": 1.0})
    assert out.result == AttemptResult.WRONG


def test_legacy_rows_still_graded():
    assert validate({"left": ["R"], "right": ["P"]}, {"choice": "left"}).result == AttemptResult.CORRECT
    assert validate({"left": ["P"], "right": ["R"]}, {"choice": "right"}).result == AttemptResult.CORRECT
    assert validate({"left": ["Q"], "right": ["R", "B", "P"]}, {"choice": "equal"}).result == AttemptResult.CORRECT
    assert validate({"left": ["R"], "right": ["P"]}, {"choice": "right"}).result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Scoring ---


def test_scoring_correct_plus5_wrong_minus2():
    answer = answer_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert score_heavier_side(validate(answer, attempt("equal"))) == 5.0
    assert score_heavier_side(validate(answer, attempt("white"))) == -2.0


# --- Generator ---


def test_question_for_fen_rejects_over_10_percent():
    # 8 vs 3 = 62% difference: rejected.
    assert gen_mod.question_for_fen("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1") is None
    assert gen_mod.question_for_fen("not a fen") is None


def test_question_for_fen_accepts_eligible():
    data = gen_mod.question_for_fen("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert data is not None
    assert data["expected"] == "equal"


def test_generated_puzzles_satisfy_10_percent(db_session):
    rng = random.Random(1234)
    for _ in range(15):
        puzzle = gen_mod.create_puzzle(db_session, rng)
        assert puzzle.fen
        white, black = mat.material_from_fen(puzzle.fen)
        larger = max(white, black)
        assert larger == 0 or abs(white - black) / larger <= 0.10
        assert puzzle.answer_json == {"fen": puzzle.fen}
        assert puzzle.position_json["fen"] == puzzle.fen


def test_generator_handles_each_desired_category():
    rng = random.Random(999)
    for category in ("white", "black", "equal"):
        data = gen_mod.generate_question_data(rng, desired=category)
        assert mat.classify_fen(data["fen"]) in {"white", "black", "equal"}


def test_generator_desired_category_hint(db_session):
    rng = random.Random(7)
    for want in ("white", "black", "equal"):
        data = gen_mod.generate_question_data(rng, desired=want)
        # Bounded hint: usually hits, always eligible.
        white, black = data["white"], data["black"]
        assert mat.is_material_difference_acceptable(white, black)


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
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.answer_json == {"fen": puzzle.fen}
        assert puzzle.position_json["fen"] == puzzle.fen
        white, black = mat.material_from_fen(puzzle.fen)
        larger = max(white, black)
        assert larger == 0 or abs(white - black) / larger <= 0.10
        expected = "white" if white > black else "black" if black > white else "equal"
        distribution[expected] = distribution.get(expected, 0) + 1
        assert validate(puzzle.answer_json, {"choice": expected}).result == AttemptResult.CORRECT
        assert puzzle.prompt_fa and puzzle.explanation
        assert not puzzle.is_published and puzzle.status == "validated"
    assert distribution.get("equal", 0) >= 2
    assert distribution.get("white", 0) >= 2
    assert distribution.get("black", 0) >= 2


def test_seed_rejects_broken_puzzles():
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"fen": "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "answer": "white"})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"fen": "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1", "answer": "white"})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"fen": "bad", "answer": "equal"})


# --- API ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_api_list_hides_answer(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    assert body[0]["fen"]
    assert body[0]["position_json"]["fen"] == body[0]["fen"]


@pytest.fixture
def published_pool(db_session):
    seed_mod.seed_db(db_session)
    puzzle_ids = publish_generated_pool(db_session, SLUG, gen_mod.create_puzzle, count=19)
    if len(puzzle_ids) < 20:
        data = gen_mod.question_for_fen("q3k2r/8/8/8/8/8/8/3QK2R w - - 0 1")
        assert data is not None
        stage_validated_puzzle(
            db_session,
            {
                "exercise_slug": SLUG,
                "fen": data["fen"],
                "position_json": {"fen": data["fen"], "mode": "standard"},
                "answer_json": {"fen": data["fen"]},
                "hint_json": data["hint_json"],
                "prompt_fa": data["prompt_fa"],
                "explanation": data["explanation"],
                "initial_rating": 800.0,
            },
            source=SOURCE_GENERATED,
            source_reference=f"generator:{SLUG}",
        )
        db_session.commit()
        publish_staged_puzzles(db_session, SLUG)


def test_api_next_hides_answer(client, db_session, published_pool):
    res = client.post("/api/v1/heavier-side/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    assert body["fen"]
    assert "correct_answer" not in body
    assert "white_material" not in body
    assert "black_material" not in body


def test_api_next_puzzle_satisfies_gate(client, db_session, published_pool):
    for _ in range(5):
        res = client.post("/api/v1/heavier-side/next", json={})
        assert res.status_code == 200
        fen = res.json()["fen"]
        white, black = mat.material_from_fen(fen)
        larger = max(white, black)
        assert larger == 0 or abs(white - black) / larger <= 0.10


def test_api_submit_correct_and_wrong(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    expected = mat.classify_fen(puzzle.fen)
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": expected}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 5.0

    wrong_choice = "white" if expected != "white" else "black"
    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": wrong_choice}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"
    assert bad.json()["score"] == -2.0


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_api_invalid_puzzle_id_404(client, db_session):
    res = client.get("/api/v1/puzzles/999999")
    assert res.status_code == 404


def test_speed_lifecycle(client, db_session, published_pool):
    started = client.post("/api/v1/heavier-side/sessions", json={})
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    buf = client.post(f"/api/v1/heavier-side/sessions/{session_id}/puzzles", json={"count": 20})
    assert buf.status_code == 200
    assert len(buf.json()) == 20
    for entry in buf.json():
        assert "answer_json" not in entry
    clock = client.post(f"/api/v1/heavier-side/sessions/{session_id}/start")
    assert clock.status_code == 200
    first = buf.json()[0]
    expected = mat.classify_fen(first["fen"])
    sub = client.post(
        f"/api/v1/heavier-side/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"choice": expected}},
        headers=make_auth_headers(db_session),
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    report = client.get(f"/api/v1/heavier-side/sessions/{session_id}/report")
    assert report.status_code == 200
    assert report.json()["session"]["attempted"] == 1
    assert report.json()["entries"][0]["fen"] == first["fen"]
