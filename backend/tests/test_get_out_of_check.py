"""Get Out of Check: escape validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.get_out_of_check import seed as seed_mod
from app.modules.get_out_of_check.validator import SLUG, escaping_moves, is_escaping_move, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(fen: str) -> dict:
    return {"fen": fen}


def attempt(frm: object, to: object, promotion: object = None) -> dict:
    body: dict = {"from": frm, "to": to}
    if promotion is not None:
        body["promotion"] = promotion
    return body


# --- Validator: correct escapes ---


def test_king_escape():
    out = validate(answer_for("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"), attempt("e1", "d1"))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["d1", "e1"], "missed": [], "wrong": []}


def test_capture_attacker():
    assert validate(answer_for("4k3/8/8/8/1b6/8/2N5/4K3 w - - 0 1"), attempt("c2", "b4")).result == AttemptResult.CORRECT


def test_block_line_check():
    assert validate(answer_for("4r3/8/8/8/8/3B4/8/4K3 w - - 0 1"), attempt("d3", "e2")).result == AttemptResult.CORRECT


def test_escape_knight_check():
    assert validate(answer_for("4k3/8/8/8/8/5n2/6P1/4K3 w - - 0 1"), attempt("g2", "f3")).result == AttemptResult.CORRECT


def test_escape_pawn_check():
    assert validate(answer_for("4k3/8/8/8/8/8/3p4/4K3 w - - 0 1"), attempt("e1", "d2")).result == AttemptResult.CORRECT


def test_double_check_only_king_moves():
    fen = "4k3/8/8/8/1b6/5n2/8/4K3 w - - 0 1"
    assert validate(answer_for(fen), attempt("e1", "d1")).result == AttemptResult.CORRECT
    # In double check only king moves resolve: every escape starts on e1.
    assert all(m.startswith("e1") for m in escaping_moves(fen))


def test_promotion_escape():
    fen = "3k3n/5KP1/8/8/8/8/8/8 w - - 0 1"
    assert chess.Board(fen).is_check() is True
    assert validate(answer_for(fen), attempt("g7", "h8", "q")).result == AttemptResult.CORRECT
    # Capturing the sole checker resolves the check whatever it promotes to.
    assert validate(answer_for(fen), attempt("g7", "h8", "n")).result == AttemptResult.CORRECT
    assert validate(answer_for(fen), attempt("g7", "h8")).result == AttemptResult.CORRECT
    # Pushing without capturing ignores the check entirely.
    assert validate(answer_for(fen), attempt("g7", "g8", "q")).result == AttemptResult.WRONG
    # Unknown promotion letters fail safely.
    assert validate(answer_for(fen), attempt("g7", "h8", "k")).result == AttemptResult.WRONG


def test_multiple_escapes_all_accepted():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    assert len(escaping_moves(fen)) > 1
    for uci in ("e1d1", "e1f1", "e1e2"):
        out = validate(answer_for(fen), attempt(uci[:2], uci[2:]))
        assert out.result == AttemptResult.CORRECT, uci


# --- Validator: wrong moves ---


def test_legal_move_leaving_check_is_wrong():
    # Qd8 ignores the b1 rook's check on e1.
    out = validate(answer_for("3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"), attempt("d4", "d8"))
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": [], "wrong": ["d4", "d8"]}


def test_illegal_move_is_wrong():
    # Pinned bishop cannot leave the a1 rook's line.
    assert validate(answer_for("4k3/8/8/8/1q6/8/2P5/r1B1K3 w - - 0 1"), attempt("c1", "d2")).result == AttemptResult.WRONG


def test_illegal_king_destination_is_wrong():
    # d1 and f1 are covered by the checking queen.
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    assert validate(answer_for(fen), attempt("e1", "d1")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("e1", "f1")).result == AttemptResult.WRONG


def test_move_from_empty_square_is_wrong():
    assert validate(answer_for("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"), attempt("e5", "e6")).result == AttemptResult.WRONG


def test_position_not_in_check_rejects_everything():
    fen = "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"
    assert chess.Board(fen).is_check() is False
    assert validate(answer_for(fen), attempt("a1", "a8")).result == AttemptResult.WRONG


# --- Validator: malformed input never crashes ---


def test_malformed_answers_are_safe_wrong():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    assert validate(answer_for(fen), {}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"from": "e1"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"to": "d1"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("e9", "d1")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("e1", "z0")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt(42, "d1")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("e1", None)).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("e1", "d1", "k")).result == AttemptResult.WRONG
    assert validate(answer_for("not a fen!!"), attempt("e1", "d1")).result == AttemptResult.WRONG
    assert validate({}, attempt("e1", "d1")).result == AttemptResult.WRONG
    assert validate(None, attempt("e1", "d1")).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(fen), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_client_cannot_force_correctness():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    out = validate(answer_for(fen), {"from": "e1", "to": "d2", "result": "correct", "score": 1.0})
    assert out.result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (independent recomputation) ---


def _independent_escapes(fen: str) -> list[str]:
    board = chess.Board(fen)
    if not board.is_check():
        return []
    mover = board.turn
    found = []
    for move in board.legal_moves:
        board.push(move)
        try:
            king = board.king(mover)
            if king is not None and not board.is_attacked_by(not mover, king):
                found.append(move.uci())
        finally:
            board.pop()
    return sorted(found)


def _to_uci(frm: str, to: str, promotion: str | None) -> str:
    prom = {"q": "q", "r": "r", "b": "b", "n": "n"}.get(promotion) if promotion else ""
    return f"{frm}{to}{prom}"


def test_seed_count_and_examples_valid(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen
        assert chess.Board(puzzle.fen).is_check() is True
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": "standard"}
        example = puzzle.answer_json["example"]
        uci = _to_uci(example["from"], example["to"], example.get("promotion"))
        assert uci in _independent_escapes(puzzle.fen), puzzle.fen
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len({p.initial_rating for p in puzzles}) >= 5
    # Validator agrees with independent recomputation on every example.
    for puzzle in puzzles:
        example = puzzle.answer_json["example"]
        out = validate(
            puzzle.answer_json,
            {"from": example["from"], "to": example["to"], **({"promotion": example["promotion"]} if example.get("promotion") else {})},
        )
        assert out.result == AttemptResult.CORRECT, puzzle.fen


def test_seed_single_escape_puzzle(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    singles = [p for p in puzzles if len(_independent_escapes(p.fen)) == 1]
    assert len(singles) >= 1


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
        json={"puzzle_id": puzzle.id, "answer": {"from": "e1", "to": "f2"}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"from": "e1", "to": "f2"}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
