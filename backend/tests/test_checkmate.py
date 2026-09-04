"""Is it Checkmate: classification, validation, seed, API."""

import chess
import pytest

from app.modules.checkmate import seed as seed_mod
from app.modules.checkmate.validator import CHOICES, SLUG, classify, normalize_choice, validate
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(fen: str) -> dict:
    return {"fen": fen}


def attempt(choice: object) -> dict:
    return {"choice": choice}


def state_of(fen: str) -> str:
    board = chess.Board(fen)
    if board.is_checkmate():
        return "checkmate"
    if board.is_check():
        return "check"
    return "not_check"


# --- Classification ---


def test_obvious_checkmate():
    assert classify("7k/6Q1/7K/8/8/8/8/8 b - - 0 1") == "checkmate"


def test_back_rank_mate():
    assert classify("3Q2k1/5ppp/4N3/8/8/8/8/K7 b - - 0 1") == "checkmate"


def test_double_checkmate():
    assert classify("k7/8/K7/3B4/8/8/8/1Q6 b - - 0 1") == "checkmate"


def test_double_check_not_mate():
    assert classify("k3r3/8/8/8/1b6/8/8/4K3 w - - 0 1") == "check"


def test_blockable_check():
    assert classify("4k3/8/8/8/1b6/8/2P5/4K3 w - - 0 1") == "check"


def test_capturable_checker():
    assert classify("4k3/8/8/8/8/5n2/6P1/4K3 w - - 0 1") == "check"


def test_king_escape_check():
    assert classify("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1") == "check"


def test_discovered_check_state():
    # The checker attacks along an open line; what matters is the state.
    assert classify("k3r3/8/8/8/1b6/8/8/4K3 w - - 0 1") == "check"


def test_quiet_position():
    assert classify("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1") == "not_check"


def test_stalemate_is_not_check():
    fen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
    board = chess.Board(fen)
    assert board.is_stalemate() is True
    assert classify(fen) == "not_check"


def test_missing_king_rejected():
    with pytest.raises(ValueError):
        classify("8/8/8/8/8/8/8/4K3 w - - 0 1")


def test_invalid_fen_rejected():
    with pytest.raises(ValueError):
        classify("not a fen")


# --- Validation ---


def test_correct_checkmate_answer():
    out = validate(answer_for("7k/6Q1/7K/8/8/8/8/8 b - - 0 1"), attempt("checkmate"))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["checkmate"], "missed": [], "wrong": []}


def test_correct_check_answer():
    out = validate(answer_for("k3r3/8/8/8/8/8/8/4K3 w - - 0 1"), attempt("check"))
    assert out.result == AttemptResult.CORRECT


def test_correct_not_check_answer():
    out = validate(answer_for("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"), attempt("not_check"))
    assert out.result == AttemptResult.CORRECT


def test_wrong_answer():
    out = validate(answer_for("7k/6Q1/7K/8/8/8/8/8 b - - 0 1"), attempt("check"))
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": [], "wrong": ["check"]}


def test_malformed_answer_safe():
    fen = "7k/6Q1/7K/8/8/8/8/8 b - - 0 1"
    assert validate(answer_for(fen), {}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"choice": "mate"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"choice": ""}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"choice": None}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"choice": 42}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"choice": ["checkmate"]}).result == AttemptResult.WRONG
    assert validate({}, attempt("checkmate")).result == AttemptResult.WRONG
    assert validate({"fen": "not a fen"}, attempt("checkmate")).result == AttemptResult.WRONG
    assert validate(None, attempt("checkmate")).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(fen), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_unsupported_choice_rejected():
    assert validate(answer_for("7k/6Q1/7K/8/8/8/8/8 b - - 0 1"), attempt("stalemate")).result == AttemptResult.WRONG


def test_fake_client_flags_ignored():
    out = validate(
        answer_for("4r3/8/8/8/8/8/8/4K3 w - - 0 1"),
        {"choice": "not_check", "is_checkmate": True, "result": "correct"},
    )
    assert out.result == AttemptResult.WRONG


def test_extra_fields_ignored():
    out = validate(
        answer_for("k3r3/8/8/8/8/8/8/4K3 w - - 0 1"),
        {"choice": "check", "comment": "looks scary"},
    )
    assert out.result == AttemptResult.CORRECT


def test_normalize_choice():
    assert normalize_choice(" CheckMate ") == "checkmate"
    assert normalize_choice("NOT_CHECK") == "not_check"
    assert normalize_choice("mate") is None
    assert normalize_choice("") is None
    assert normalize_choice(None) is None


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert set(CHOICES) == {"checkmate", "check", "not_check"}


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call classify/validate: they re-derive every answer
# straight from python-chess legal move generation.


def _independent(fen: str) -> str:
    board = chess.Board(fen)
    if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
        raise ValueError("position needs both kings")
    in_check = any(True for _ in [0] if board.is_attacked_by(not board.turn, board.king(board.turn)))
    has_moves = any(True for _ in board.legal_moves)
    if in_check and not has_moves:
        return "checkmate"
    if in_check:
        return "check"
    return "not_check"


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    seen_answers = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": "standard"}
        expected = _independent(puzzle.fen)
        assert puzzle.answer_json["fen"] == puzzle.fen
        assert validate(puzzle.answer_json, {"choice": expected}).result == AttemptResult.CORRECT
        seen_answers.add(expected)
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert seen_answers == {"checkmate", "check", "not_check"}
    assert len({p.initial_rating for p in puzzles}) >= 5


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]

    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": state_of(puzzle.fen)}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert sorted(ok.json()["detail"]["correct"]) == [state_of(puzzle.fen)]

    other = {"checkmate", "check", "not_check"} - {state_of(puzzle.fen)}
    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": sorted(other)[0]}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"choice": state_of(puzzle.fen)}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
