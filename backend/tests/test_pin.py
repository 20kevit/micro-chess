"""Pin: pin detection, validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.pin import seed as seed_mod
from app.modules.pin.validator import SLUG, creates_pin, find_pins, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(fen: str) -> dict:
    return {"fen": fen}


def attempt(frm: object, to: object, promotion: object = None) -> dict:
    body: dict = {"from": frm, "to": to}
    if promotion is not None:
        body["promotion"] = promotion
    return body


def pin_set(fen: str) -> set[tuple[str, str, str]]:
    return {(p["pinned"], p["behind"], p["pinner"]) for p in find_pins(fen)}


def after_move(fen: str, uci: str) -> str:
    board = chess.Board(fen)
    board.push(chess.Move.from_uci(uci))
    return board.fen()


# --- Pin detection: absolute pins ---


def test_absolute_rook_pin():
    pins = pin_set("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1")
    assert pins == set()
    board = chess.Board("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1")
    board.push(chess.Move.from_uci("a1e1"))
    after = pin_set(board.fen())
    assert ("e6", "e8", "e1") in after
    assert find_pins(board.fen())[0]["absolute"] is True


def test_absolute_bishop_pin():
    assert pin_set("7k/6p1/8/8/8/8/8/2B1K3 w - - 0 1") == set()
    assert ("g7", "h8", "b2") in pin_set("7k/6p1/8/8/8/8/1B6/2B1K3 w - - 0 1")


def test_absolute_queen_pin():
    assert ("e6", "e8", "e2") in pin_set("4k3/8/4b3/8/8/8/4Q3/4K3 w - - 0 1")


# --- Pin detection: relative pins ---


def test_relative_rook_pin():
    assert ("e6", "e8", "e1") in pin_set(after_move("k3q3/8/4r3/8/8/8/8/R4K2 w KQkq - 0 1", "a1e1"))


def test_relative_bishop_pin():
    assert ("b4", "c5", "a3") in pin_set(after_move("k7/8/8/2q5/1n6/8/8/2B1K3 w - - 0 1", "c1a3"))


def test_relative_queen_pin():
    assert ("e5", "e7", "e2") in pin_set(after_move("k7/4q3/8/4n3/8/8/8/3QK3 w - - 0 1", "d1e2"))


# --- Pin detection: pinned piece types ---


def test_pinned_knight_bishop_rook_queen_pawn():
    assert ("e6", "e8", "e1") in pin_set(after_move("4k3/8/4n3/8/8/8/8/R3K3 w - - 0 1", "a1e1"))  # knight
    assert ("e6", "e8", "e2") in pin_set(after_move("4k3/8/4b3/8/8/8/8/3QK3 w - - 0 1", "d1e2"))  # bishop
    assert ("e6", "e8", "e1") in pin_set(after_move("k3q3/8/4r3/8/8/8/8/R3K3 w - - 0 1", "a1e1"))  # rook
    assert ("c4", "c8", "c1") in pin_set(after_move("2k5/8/8/8/2q5/8/8/R3K3 w - - 0 1", "a1c1"))  # queen
    assert ("g7", "h8", "b2") in pin_set(after_move("7k/6p1/8/8/8/8/1B6/2B1K3 w - - 0 1", "c1b2"))  # pawn


def test_king_behind_is_absolute():
    pins = find_pins("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1")
    assert pins == []


def test_non_king_behind_is_relative():
    pins = find_pins(after_move("k3q3/8/4r3/8/8/8/8/R3K3 w KQkq - 0 1", "a1e1"))
    assert len(pins) == 1
    assert pins[0]["absolute"] is False


# --- Validation: correct moves ---


def test_legal_move_creating_pin_is_correct():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1"), attempt("a1", "e1"))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["a1", "e1"], "missed": [], "wrong": []}


def test_black_to_move_pin_is_correct():
    out = validate(answer_for("3qk3/8/8/8/8/8/3P4/4K3 b - - 0 1"), attempt("d8", "a5"))
    assert out.result == AttemptResult.CORRECT


def test_multiple_correct_moves_all_accepted():
    fen = "k7/4q3/8/4n3/n7/8/3Q4/1R4K1 w - - 0 1"
    assert validate(answer_for(fen), attempt("b1", "a1")).result == AttemptResult.CORRECT
    assert validate(answer_for(fen), attempt("d2", "e2")).result == AttemptResult.CORRECT


# --- Validation: wrong moves ---


def test_legal_move_without_pin_is_wrong():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1"), attempt("a1", "a8"))
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": [], "wrong": ["a1", "a8"]}


def test_illegal_move_is_wrong():
    # Rook cannot move diagonally: not even a legal move.
    assert validate(answer_for("4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1"), attempt("a1", "h8")).result == AttemptResult.WRONG


def test_ordinary_attack_is_not_a_pin():
    # Qd1-d3 attacks squares but pins nothing behind any of them.
    out = validate(answer_for("k7/4q3/8/4n3/8/8/8/3QK3 w - - 0 1"), attempt("d1", "d3"))
    assert out.result == AttemptResult.WRONG


def test_knight_attack_is_not_a_pin():
    # Knights never create classical pins, even when they attack.
    assert creates_pin("4k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "b5", "d6") is False


def test_pawn_attack_is_not_a_pin():
    assert creates_pin("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4", "d5") is False


def test_existing_pin_without_new_pin_is_wrong():
    # f6 is already pinned; Ra1-a2 changes nothing about pins.
    fen = "7k/4q3/4nn2/8/8/8/1B6/R5K1 w - - 0 1"
    assert validate(answer_for(fen), attempt("a1", "a2")).result == AttemptResult.WRONG


def test_capture_removing_pin_is_wrong():
    # Qxe6 removes the knight instead of pinning it.
    out = validate(answer_for("4k3/8/4n3/8/3Q4/8/8/R5K1 w - - 0 1"), attempt("d4", "e6"))
    assert out.result == AttemptResult.WRONG


# --- Validation: malformed input never crashes ---


def test_malformed_answers_are_safe_wrong():
    fen = "4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1"
    assert validate(answer_for(fen), {}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"from": "a1"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {"to": "e1"}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("a9", "e1")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("a1", "z0")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt(42, "e1")).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("a1", None)).result == AttemptResult.WRONG
    assert validate(answer_for(fen), attempt("a1", "e1", "k")).result == AttemptResult.WRONG
    assert validate(answer_for("not a fen!!"), attempt("a1", "e1")).result == AttemptResult.WRONG
    assert validate({}, attempt("a1", "e1")).result == AttemptResult.WRONG
    assert validate(None, attempt("a1", "e1")).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(fen), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_validate_ignores_client_side_answer():
    answer = {"fen": "4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1"}
    out = validate(answer, {"from": "a1", "to": "a2", "squares": ["e6"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": [], "wrong": ["a1", "a2"]}


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call find_pins/creates_pin: they regenerate pins with a
# separately written ray walk over python-chess squares.


def _independent_pins(fen: str) -> set[tuple[str, str, str]]:
    board = chess.Board(fen)
    sliding = {
        chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
        chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
        chess.QUEEN: [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)],
    }
    found = set()
    for slider_sq in chess.SQUARES:
        slider = board.piece_at(slider_sq)
        if slider is None or slider.piece_type not in sliding:
            continue
        fx, rk = chess.square_file(slider_sq), chess.square_rank(slider_sq)
        for dx, dy in sliding[slider.piece_type]:
            met = []
            f, r = fx + dx, rk + dy
            while 0 <= f < 8 and 0 <= r < 8:
                occ = chess.square(f, r)
                if board.piece_at(occ) is not None:
                    met.append(occ)
                    if len(met) == 2:
                        break
                f += dx
                r += dy
            if len(met) == 2:
                middle, behind = met
                if (
                    board.piece_at(middle).color != slider.color
                    and board.piece_at(behind).color != slider.color
                ):
                    found.add(
                        (chess.square_name(middle), chess.square_name(behind), chess.square_name(slider_sq))
                    )
    return found


def _independent_new_pins(fen: str, frm: str, to: str) -> set[tuple[str, str, str]]:
    board = chess.Board(fen)
    before = _independent_pins(fen)
    move = chess.Move(chess.parse_square(frm), chess.parse_square(to))
    if move not in board.legal_moves:
        return set()
    board.push(move)
    try:
        after = _independent_pins(board.fen())
    finally:
        board.pop()
    return after - before


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    seen_fens = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": "standard"}
        example = puzzle.answer_json["example"]
        assert _independent_new_pins(puzzle.fen, example["from"], example["to"]), puzzle.fen
        # ...and the validator agrees with the independent recomputation:
        out = validate(
            puzzle.answer_json,
            {"from": example["from"], "to": example["to"]},
        )
        assert out.result == AttemptResult.CORRECT, puzzle.fen
        seen_fens.add(puzzle.fen)
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len(seen_fens) == 15
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
    assert sorted(ok.json()["detail"]["correct"]) == sorted([example["from"], example["to"]])

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


def test_missing_puzzle_returns_404(client, db_session):
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": 999999, "answer": {"from": "e2", "to": "e4"}, "mode": "practice"},
    )
    assert res.status_code == 404
