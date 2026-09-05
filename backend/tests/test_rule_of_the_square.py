"""Rule of the Square: geometry, classification, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from app.modules.rule_of_the_square import seed as seed_mod
from app.modules.rule_of_the_square.description import describe_position
from app.modules.rule_of_the_square.validator import (
    CAN_CATCH,
    CANNOT_CATCH,
    SLUG,
    evaluate,
    square_squares,
    validate,
)


def _fen(pawn: str, white_pawn: bool, king: str, own_king: str, turn: str) -> str:
    board = chess.Board.empty()
    pawn_color = chess.WHITE if white_pawn else chess.BLACK
    board.set_piece_at(chess.parse_square(pawn), chess.Piece(chess.PAWN, pawn_color))
    board.set_piece_at(chess.parse_square(king), chess.Piece(chess.KING, not pawn_color))
    board.set_piece_at(chess.parse_square(own_king), chess.Piece(chess.KING, pawn_color))
    board.turn = chess.WHITE if turn == "w" else chess.BLACK
    return board.fen()


def answer_for(fen: str) -> dict:
    return {"fen": fen}


# --- Rule calculation ---


def test_white_pawn_inside_catches():
    assert evaluate(_fen("e4", True, "e8", "a1", "w"))["expected"] == CAN_CATCH


def test_white_pawn_outside_fails():
    assert evaluate(_fen("e4", True, "h3", "a1", "w"))["expected"] == CANNOT_CATCH


def test_black_pawn_inside_catches():
    assert evaluate(_fen("e5", False, "e1", "h8", "b"))["expected"] == CAN_CATCH


def test_black_pawn_outside_fails():
    assert evaluate(_fen("e5", False, "d7", "h8", "w"))["expected"] == CANNOT_CATCH


def test_boundary_corner_inside_catches():
    info = evaluate(_fen("e4", True, "h4", "a1", "w"))
    assert info["expected"] == CAN_CATCH
    assert "h4" in square_squares("e4", True)


def test_boundary_just_outside_fails():
    info = evaluate(_fen("e4", True, "h3", "a1", "w"))
    assert info["expected"] == CANNOT_CATCH
    assert "h3" not in square_squares("e4", True)


def test_starting_rank_double_step_shrinks_square():
    # e2 threatens e4: the zone is drawn as if from e3 (ranks 3-8).
    assert square_squares("e2", True) == square_squares("e3", True)
    assert "h2" not in square_squares("e2", True)
    assert evaluate(_fen("e2", True, "e8", "a1", "w"))["expected"] == CAN_CATCH
    assert evaluate(_fen("e2", True, "h2", "a1", "w"))["expected"] == CANNOT_CATCH


def test_black_starting_rank_double_step():
    assert "a1" in square_squares("e7", False)
    assert "h8" not in square_squares("e7", False)
    assert evaluate(_fen("e7", False, "a1", "h8", "b"))["expected"] == CAN_CATCH


def test_edge_file_clipping():
    zone = square_squares("a4", True)
    assert zone == {f"{f}{r}" for f in "abcde" for r in range(4, 9)}
    assert evaluate(_fen("a4", True, "b7", "h1", "w"))["expected"] == CAN_CATCH
    assert evaluate(_fen("a4", True, "c3", "h1", "w"))["expected"] == CANNOT_CATCH


def test_central_file_zone():
    zone = square_squares("g5", True)
    assert zone == {f"{f}{r}" for f in "defgh" for r in range(5, 9)}


def test_defender_to_move_steps_in():
    # Same position, opposite turns: shut out with White to move...
    assert evaluate(_fen("e4", True, "h3", "a1", "w"))["expected"] == CANNOT_CATCH
    # ...but Black to move steps into the square.
    assert evaluate(_fen("e4", True, "h3", "a1", "b"))["expected"] == CAN_CATCH


def test_attacker_advance_escapes_corner():
    # g1 sits on the current square's corner, but after ...d3 it falls out.
    assert evaluate(_fen("d4", False, "g1", "h8", "b"))["expected"] == CANNOT_CATCH


def test_tempo_corner_inside_is_not_enough():
    # The king stands inside the drawn square yet loses the race: naive
    # inside-only logic would accept, exact race play rejects.
    fen = _fen("d4", False, "g1", "h8", "b")
    assert "g1" in square_squares("d4", False)
    assert evaluate(fen)["expected"] == CANNOT_CATCH
    assert validate({"fen": fen}, {"answer": "CAN_CATCH"}).result == AttemptResult.WRONG
    assert validate({"fen": fen}, {"answer": "CANNOT_CATCH"}).result == AttemptResult.CORRECT


def test_rule_matches_exact_race_play():
    for item in seed_mod.PUZZLES:
        fen = seed_mod.build_fen(item)
        assert evaluate(fen)["expected"] == _race(fen), fen


def _race(fen: str) -> str:
    """Independent ground truth: exhaustive optimal K-vs-P race play."""
    from functools import lru_cache

    b0 = chess.Board(fen)
    pawn_sq = next(s for s in chess.SQUARES if (p := b0.piece_at(s)) and p.piece_type == chess.PAWN)
    pc = b0.piece_at(pawn_sq).color

    @lru_cache(maxsize=None)
    def solve(psq: int | None, ksq: int, turn: bool) -> bool:
        if psq is None:
            return True
        pr = chess.square_rank(psq)
        if (pc == chess.WHITE and pr == 7) or (pc == chess.BLACK and pr == 0):
            return False
        if turn != pc:
            return any(to == psq or solve(psq, to, pc) for to in chess.SquareSet(chess.BB_KING_ATTACKS[ksq]))
        f, r = chess.square_file(psq), pr
        d = 1 if pc == chess.WHITE else -1
        opts = [chess.square(f, r + d)]
        if (pc == chess.WHITE and r == 1) or (pc == chess.BLACK and r == 6):
            opts.append(chess.square(f, r + 2 * d))
        return all(solve(o, ksq, not pc) for o in opts)

    dk = next(
        s for s in chess.SQUARES if (p := b0.piece_at(s)) and p.piece_type == chess.KING and p.color != pc
    )
    return CAN_CATCH if solve(pawn_sq, dk, b0.turn) else CANNOT_CATCH


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Classification ---


def test_validate_correct_and_wrong():
    fen = _fen("e4", True, "e8", "a1", "w")
    assert validate(answer_for(fen), {"answer": "CAN_CATCH"}).result == AttemptResult.CORRECT
    assert validate(answer_for(fen), {"answer": "can_catch"}).result == AttemptResult.CORRECT
    assert validate(answer_for(fen), {"answer": "  cannot_catch "}).result == AttemptResult.WRONG


def test_validate_accepts_answer_key_shapes():
    fen = _fen("e4", True, "h3", "a1", "w")
    assert validate(answer_for(fen), {"answer": "CANNOT_CATCH"}).result == AttemptResult.CORRECT
    for bad in ("", "   ", "yes", "1", 123, None, {}, {"answer": "CAN_CATCH"}):
        assert validate(answer_for(fen), {"answer": bad}).result == AttemptResult.WRONG
    assert validate(answer_for(fen), {}).result == AttemptResult.WRONG


def test_validate_detail_carries_geometry():
    fen = _fen("e4", True, "e8", "a1", "w")
    out = validate(answer_for(fen), {"answer": "CAN_CATCH"})
    assert out.detail["expected"] == CAN_CATCH
    assert out.detail["correct"] == [CAN_CATCH]
    assert set(out.detail["corners"]) == {"a4", "a8", "h4", "h8"}
    assert "e8" in out.detail["square"]
    bad = validate(answer_for(fen), {"answer": "CANNOT_CATCH"})
    assert bad.detail["missed"] == [CAN_CATCH]
    assert bad.detail["wrong"] == ["CANNOT_CATCH"]


def test_invalid_positions_fail_safe():
    assert validate({"fen": "junk"}, {"answer": "CAN_CATCH"}).result == AttemptResult.WRONG
    assert validate({}, {"answer": "CAN_CATCH"}).result == AttemptResult.WRONG
    two_pawns = "4k3/8/8/8/3PP3/8/8/4K3 w - - 0 1"
    assert validate(answer_for(two_pawns), {"answer": "CAN_CATCH"}).result == AttemptResult.WRONG


def test_client_fen_ignored():
    fen = _fen("e4", True, "e8", "a1", "w")
    out = validate(answer_for(fen), {"answer": "CAN_CATCH", "fen": _fen("e4", True, "h3", "a1", "w")})
    assert out.result == AttemptResult.CORRECT


# --- Seed ---


def test_seed_count_idempotent_split(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    outcomes = [evaluate(p.answer_json["fen"])["expected"] for p in puzzles]
    assert 7 <= outcomes.count(CAN_CATCH) <= 8


def test_seed_positions_legal_and_deterministic(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    seen = set()
    colors = set()
    for puzzle in puzzles:
        board = chess.Board(puzzle.fen)
        pieces = [board.piece_at(sq) for sq in chess.SQUARES if board.piece_at(sq)]
        assert len(pieces) == 3  # minimum material: K + k + pawn
        assert sum(1 for p in pieces if p.piece_type == chess.PAWN) == 1
        kings = [sq for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.piece_type == chess.KING]
        assert chess.square_distance(kings[0], kings[1]) >= 2
        assert not board.is_check()
        assert puzzle.answer_json == {"fen": puzzle.fen}
        assert puzzle.position_json == {"mode": "square-rule"}
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        assert puzzle.explanation == seed_mod.explain(evaluate(puzzle.fen), _item_for(puzzle.fen))
        colors.add(board.piece_at(next(
            sq for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.piece_type == chess.PAWN
        )).color)
        seen.add(puzzle.fen)
        # Validator agrees with the independent rule on both answers.
        expected = evaluate(puzzle.fen)["expected"]
        assert validate(puzzle.answer_json, {"answer": expected}).result == AttemptResult.CORRECT
    assert len(seen) == 15  # no duplicate positions
    assert colors == {chess.WHITE, chess.BLACK}
    assert len({p.initial_rating for p in puzzles}) >= 5


def _item_for(fen: str) -> dict:
    board = chess.Board(fen)
    pawn_sq = next(s for s in chess.SQUARES if (p := board.piece_at(s)) and p.piece_type == chess.PAWN)
    return {"pawn": chess.square_name(pawn_sq), "white": True, "king": "", "own_king": "", "turn": "w"}


def test_seed_hints_hide_verdict(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    for puzzle in puzzles:
        for hint in puzzle.hint_json["hints"]:
            assert "می‌رسد" not in hint["text_fa"]
            assert "نمی‌رسد" not in hint["text_fa"]


def test_description_content():
    text = describe_position(_fen("e4", True, "e8", "a1", "w"))
    assert "e4" in text and "e8" in text
    assert "مربع" not in text and "می‌رسد" not in text
    with pytest.raises(ValueError):
        describe_position("not-a-fen")


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_api_board_visible_answer_hidden(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    for entry in body:
        assert entry["fen"]  # the board must render
        assert "answer_json" not in entry
    dumped = res.text
    for token in ("answer_json", "CAN_CATCH", "CANNOT_CATCH", "correct_answer", "solution"):
        assert token not in dumped


def test_api_correct_wrong_submit(client, db_session):
    puzzle = _seeded(db_session)
    expected = evaluate(puzzle.fen)["expected"]
    other = CANNOT_CATCH if expected == CAN_CATCH else CAN_CATCH
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"answer": expected}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["expected"] == expected
    assert ok.json()["detail"]["corners"]

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"answer": other}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    malformed = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"answer": "yes"}, "mode": "practice"},
    )
    assert malformed.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"answer": expected}, "mode": "rated"},
    )
    assert rated.status_code == 401
