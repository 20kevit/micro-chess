"""Memory Board: reconstruction validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.memory_board import seed as seed_mod
from app.modules.memory_board.validator import (
    SLUG,
    board_turn,
    normalize_entry,
    normalize_turn,
    placement_map,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult

FEN = "4k3/8/8/8/8/8/5P2/4K2R w K - 0 1"


def answer_for(fen: str) -> dict:
    return {"fen": fen}


def attempt_for(fen: str, turn: str = "white") -> dict:
    board = chess.Board(fen)
    pieces = [
        {
            "square": chess.square_name(sq),
            "piece": piece.symbol().upper(),
            "color": "white" if piece.color == chess.WHITE else "black",
        }
        for sq, piece in board.piece_map().items()
    ]
    return {"pieces": pieces, "turn": turn}


# --- Parsing / puzzle validation ---


def test_valid_fen_parses():
    assert placement_map(FEN) == {"e8": "k", "f2": "P", "e1": "K", "h1": "R"}
    assert board_turn(FEN) == "white"


def test_invalid_fen_rejected():
    with pytest.raises(ValueError):
        placement_map("not a fen")
    with pytest.raises(ValueError):
        board_turn("8/8/8/8/8 w - - 0 1")


def test_normalize_entry():
    assert normalize_entry({"square": "E1", "piece": "k", "color": " White "}) == ("e1", "K")
    assert normalize_entry({"square": "e8", "piece": "K", "color": "black"}) == ("e8", "k")
    assert normalize_entry({"square": "e9", "piece": "K", "color": "white"}) is None
    assert normalize_entry({"square": "e1", "piece": "X", "color": "white"}) is None
    assert normalize_entry({"square": "e1", "piece": "K", "color": "red"}) is None
    assert normalize_entry({"square": "e1", "piece": "K"}) is None
    assert normalize_entry("e1") is None
    assert normalize_entry(None) is None


def test_normalize_turn():
    assert normalize_turn(" White ") == "white"
    assert normalize_turn("BLACK") == "black"
    assert normalize_turn("w") is None
    assert normalize_turn("") is None
    assert normalize_turn(None) is None
    assert normalize_turn(42) is None


# --- Reconstruction validation ---


def test_exact_reconstruction_is_correct():
    out = validate(answer_for(FEN), attempt_for(FEN))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["e1", "e8", "f2", "h1"], "missed": [], "wrong": []}


def test_wrong_square_is_wrong():
    body = attempt_for(FEN)
    pawn = next(p for p in body["pieces"] if p["square"] == "f2")
    pawn["square"] = "f3"
    out = validate(answer_for(FEN), body)
    assert out.result == AttemptResult.WRONG
    assert "f2" in out.detail["missed"]
    assert "f3" in out.detail["wrong"]


def test_missing_piece_is_wrong():
    body = attempt_for(FEN)
    body["pieces"] = body["pieces"][:-1]
    assert validate(answer_for(FEN), body).result == AttemptResult.WRONG


def test_extra_piece_is_wrong():
    body = attempt_for(FEN)
    body["pieces"].append({"square": "a3", "piece": "P", "color": "white"})
    out = validate(answer_for(FEN), body)
    assert out.result == AttemptResult.WRONG
    assert "a3" in out.detail["wrong"]


def test_wrong_color_is_wrong():
    body = attempt_for(FEN)
    pawn = next(p for p in body["pieces"] if p["square"] == "f2")
    pawn["color"] = "black"
    assert validate(answer_for(FEN), body).result == AttemptResult.WRONG


def test_wrong_piece_type_is_wrong():
    body = attempt_for(FEN)
    rook = next(p for p in body["pieces"] if p["square"] == "h1")
    rook["piece"] = "Q"
    assert validate(answer_for(FEN), body).result == AttemptResult.WRONG


def test_wrong_side_to_move_is_wrong():
    assert validate(answer_for(FEN), attempt_for(FEN, turn="black")).result == AttemptResult.WRONG


def test_order_independent_pieces():
    body = attempt_for(FEN)
    body["pieces"] = list(reversed(body["pieces"]))
    assert validate(answer_for(FEN), body).result == AttemptResult.CORRECT


def test_duplicate_square_rejected():
    body = attempt_for(FEN)
    body["pieces"].append({"square": "f2", "piece": "P", "color": "white"})
    out = validate(answer_for(FEN), body)
    assert out.result == AttemptResult.WRONG
    assert out.detail["wrong"] == ["f2"]


def test_invalid_square_rejected():
    assert validate(answer_for(FEN), {"pieces": [{"square": "i9", "piece": "P", "color": "white"}], "turn": "white"}).result == AttemptResult.WRONG


def test_invalid_piece_type_rejected():
    body = attempt_for(FEN)
    body["pieces"][0]["piece"] = "X"
    assert validate(answer_for(FEN), body).result == AttemptResult.WRONG


def test_malformed_answer_safe():
    assert validate(answer_for(FEN), {}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN), {"pieces": "e1"}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN), {"pieces": [], "turn": "white"}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN), {"turn": "white"}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN), {"pieces": []}).result == AttemptResult.WRONG
    assert validate({}, attempt_for(FEN)).result == AttemptResult.WRONG
    assert validate({"fen": "junk"}, attempt_for(FEN)).result == AttemptResult.WRONG
    assert validate(None, attempt_for(FEN)).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(FEN), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_client_correctness_flags_ignored():
    body = attempt_for(FEN)
    body["correct"] = True
    body["result"] = "correct"
    assert validate(answer_for(FEN), body).result == AttemptResult.CORRECT
    body["pieces"] = []
    assert validate(answer_for(FEN), body).result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Metadata: hidden FEN fields must not fail a visual reconstruction ---


def test_castling_rights_ignored():
    assert validate(answer_for("4k3/8/8/8/8/8/5P2/4K2R w KQ - 0 1"), attempt_for(FEN)).result == AttemptResult.CORRECT


def test_en_passant_ignored():
    assert validate(answer_for("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2"), attempt_for("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")).result == AttemptResult.CORRECT


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call placement_map/board_turn/validate: they re-derive
# everything straight from python-chess primitives.


def _independent_map(fen: str) -> dict[str, str]:
    board = chess.Board(fen)
    return {chess.square_name(sq): piece.symbol() for sq, piece in board.piece_map().items()}


def _independent_turn(fen: str) -> str:
    return "white" if chess.Board(fen).turn == chess.WHITE else "black"


def test_seed_count_and_content(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    durations = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert set(puzzle.position_json) == {"fen", "memorize_seconds"}
        assert puzzle.answer_json == {"fen": puzzle.fen}
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        durations.add(puzzle.position_json["memorize_seconds"])
    assert durations == {8, 6, 4}
    assert len({p.initial_rating for p in puzzles}) >= 5


def test_seed_positions_valid(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    counts = set()
    for puzzle in puzzles:
        board = chess.Board(puzzle.fen)
        assert board.king(chess.WHITE) is not None
        assert board.king(chess.BLACK) is not None
        assert len(_independent_map(puzzle.fen)) >= 3
        counts.add(len(_independent_map(puzzle.fen)))
        # ...and the validator agrees with the independent recomputation:
        expected = _independent_map(puzzle.fen)
        submitted = [
            {
                "square": sq,
                "piece": symbol.upper(),
                "color": "white" if symbol.isupper() else "black",
            }
            for sq, symbol in expected.items()
        ]
        out = validate(puzzle.answer_json, {"pieces": submitted, "turn": _independent_turn(puzzle.fen)})
        assert out.result == AttemptResult.CORRECT, puzzle.fen
    assert len(counts) >= 5  # varied piece counts


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def _correct_body(puzzle: Puzzle) -> dict:
    expected = _independent_map(puzzle.fen)
    turn = _independent_turn(puzzle.fen)
    return {
        "pieces": [
            {"square": sq, "piece": symbol.upper(), "color": "white" if symbol.isupper() else "black"}
            for sq, symbol in expected.items()
        ],
        "turn": turn,
    }


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    assert body[0]["position_json"]["memorize_seconds"] in (8, 6, 4)

    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": _correct_body(puzzle), "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": [], "turn": "white"}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": [], "turn": "white"}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
