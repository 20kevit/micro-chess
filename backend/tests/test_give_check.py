"""Give Check: checking-move validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.give_check import seed as seed_mod
from app.modules.give_check.validator import MODES, SLUG, checking_moves, is_checking_move, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(fen: str, mode: str = "all-checks") -> dict:
    return {"fen": fen, "mode": mode}


def attempt(frm: object, to: object, promotion: object = None) -> dict:
    body: dict = {"from": frm, "to": to}
    if promotion is not None:
        body["promotion"] = promotion
    return body


# --- Validator: correct checking moves ---


def test_rook_check():
    out = validate(answer_for("4k3/8/8/8/8/8/8/R3K3 w - - 0 1"), attempt("a1", "a8"))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["a1", "a8"], "missed": [], "wrong": []}


def test_bishop_check():
    assert validate(answer_for("4k3/8/8/8/2B5/8/8/4K3 w - - 0 1"), attempt("c4", "b5")).result == AttemptResult.CORRECT


def test_queen_check():
    assert validate(answer_for("4k3/8/8/8/8/8/8/3QK3 w - - 0 1"), attempt("d1", "h5")).result == AttemptResult.CORRECT


def test_knight_check():
    assert validate(answer_for("4k3/8/8/1N6/8/8/8/4K3 w - - 0 1"), attempt("b5", "d6")).result == AttemptResult.CORRECT


def test_pawn_check():
    assert validate(answer_for("8/8/5k2/8/4P3/8/8/4K3 w - - 0 1"), attempt("e4", "e5")).result == AttemptResult.CORRECT


def test_king_discovered_check():
    assert validate(answer_for("k7/8/8/8/8/8/K6K/R7 w - - 0 1"), attempt("a2", "b3")).result == AttemptResult.CORRECT


def test_discovered_check():
    assert validate(answer_for("7k/8/8/8/3N4/8/1B6/4K3 w - - 0 1"), attempt("d4", "f5")).result == AttemptResult.CORRECT


def test_capture_with_check():
    assert validate(answer_for("8/8/4k3/3p4/3Q4/8/8/4K3 w - - 0 1"), attempt("d4", "d5")).result == AttemptResult.CORRECT


def test_promotion_check():
    fen = "7k/6P1/8/8/8/8/8/4K3 w - - 0 1"
    assert validate(answer_for(fen), attempt("g7", "g8", "q")).result == AttemptResult.CORRECT
    # Without an explicit choice, any checking promotion counts.
    assert validate(answer_for(fen), attempt("g7", "g8")).result == AttemptResult.CORRECT
    # Underpromotion to knight does not check here.
    assert validate(answer_for(fen), attempt("g7", "g8", "n")).result == AttemptResult.WRONG
    # Nowhere to promote (king blocks the square): no candidates at all.
    assert validate(answer_for("k7/P7/8/8/8/8/8/4K3 w - - 0 1"), attempt("a7", "a8")).result == AttemptResult.WRONG


def test_modes_behave_identically():
    fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
    for mode in MODES:
        assert validate(answer_for(fen, mode), attempt("d4", "d8")).result == AttemptResult.CORRECT
        assert validate(answer_for(fen, mode), attempt("d4", "d5")).result == AttemptResult.WRONG


def test_multiple_checking_moves_all_accepted():
    fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
    assert len(checking_moves(fen)) > 1
    for uci in ("d4d8", "d4h8", "d4a4"):
        out = validate(answer_for(fen), attempt(uci[:2], uci[2:]))
        assert out.result == AttemptResult.CORRECT, uci


# --- Validator: wrong moves ---


def test_legal_non_check_is_wrong():
    out = validate(answer_for("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"), attempt("d4", "d5"))
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": [], "wrong": ["d4", "d5"]}


def test_blocked_path_is_illegal():
    # d1d8 looks like check but d7 blocks it: not even a legal move.
    assert validate(answer_for("4k3/3p4/8/8/8/8/8/3QK3 w - - 0 1"), attempt("d1", "d8")).result == AttemptResult.WRONG


def test_pinned_piece_check_is_illegal():
    # Qe2 is pinned to the e-file; leaving it exposes the white king.
    assert validate(answer_for("3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1"), attempt("e2", "h5")).result == AttemptResult.WRONG
    # ...while staying on the file with check is fine.
    assert validate(answer_for("3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1"), attempt("e2", "e7")).result == AttemptResult.CORRECT


def test_move_leaving_own_king_in_check_is_illegal():
    # White is in check; d4d8 ignores it.
    fen = "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"
    assert chess.Board(fen).is_check() is True
    assert validate(answer_for(fen), attempt("d4", "d8")).result == AttemptResult.WRONG
    # ...while blocking with check is legal and correct.
    assert validate(answer_for(fen), attempt("d4", "d1")).result == AttemptResult.CORRECT


def test_move_from_empty_square_is_wrong():
    assert validate(answer_for("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"), attempt("e5", "e6")).result == AttemptResult.WRONG


# --- Validator: malformed input never crashes ---


def test_malformed_answers_are_safe_wrong():
    fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
    assert validate(answer_for(fen), {}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"from": "d4"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"to": "d8"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("d9", "d8")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("d4", "z0")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt(42, "d8")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("d4", None)).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("g7", "g8", "k")).result == AttemptResult.WRONG
    assert validate(answer_for("not a fen!!", ), attempt("d4", "d8")).result == AttemptResult.WRONG
    assert validate({}, attempt("d4", "d8")).result == AttemptResult.WRONG
    assert validate(None, attempt("d4", "d8")).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(fen), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_client_cannot_force_correctness():
    fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
    out = validate(answer_for(fen), {"from": "d4", "to": "d5", "result": "correct", "score": 1.0})
    assert out.result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (independent recomputation) ---


def _independent_check(fen: str, frm: str, to: str, promotion: str | None) -> bool:
    board = chess.Board(fen)
    prom = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}.get(promotion) if promotion else None
    move = chess.Move(chess.parse_square(frm), chess.parse_square(to), promotion=prom)
    if move not in board.legal_moves:
        return False
    board.push(move)
    try:
        return board.is_check()
    finally:
        board.pop()


def test_seed_count_and_examples_valid(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    modes = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": puzzle.answer_json["mode"]}
        example = puzzle.answer_json["example"]
        assert _independent_check(
            puzzle.fen, example["from"], example["to"], example.get("promotion")
        ), puzzle.fen
        modes.add(puzzle.answer_json["mode"])
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert modes == set(MODES)  # both modes seeded
    assert len({p.initial_rating for p in puzzles}) >= 5
    # Validator agrees with independent recomputation on every example.
    for puzzle in puzzles:
        example = puzzle.answer_json["example"]
        out = validate(
            puzzle.answer_json,
            {"from": example["from"], "to": example["to"], **({"promotion": example["promotion"]} if example.get("promotion") else {})},
        )
        assert out.result == AttemptResult.CORRECT, puzzle.fen


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

    example = puzzle.answer_json["example"]
    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"from": example["from"], "to": example["to"]},
            "mode": "practice",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"from": "e1", "to": "e2"}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"from": "e1", "to": "e2"}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
