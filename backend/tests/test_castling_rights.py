"""Castling Rights: legality rules, validation, seed, API."""

import chess
import pytest

from app.modules.castling_rights import seed as seed_mod
from app.modules.castling_rights.validator import (
    OPTIONS,
    SLUG,
    legal_castling_options,
    normalize_option,
    validate,
)
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers


def opts(fen: str) -> set[str]:
    return set(legal_castling_options(fen))


# --- Basic legality ---


def test_all_four_legal():
    assert opts("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1") == set(OPTIONS)


def test_only_white_kingside():
    assert opts("r3kb1r/8/8/8/8/8/8/R3K2R w Kk - 0 1") == {"white_kingside"}


def test_only_white_queenside():
    assert opts("rn2k2r/8/8/8/8/8/8/R3K2R w Qq - 0 1") == {"white_queenside"}


def test_only_black_kingside():
    assert opts("r1b1k2r/8/8/8/8/8/8/R3K2R b kq - 0 1") == {"black_kingside"}


def test_only_black_queenside():
    assert opts("r3k2r/8/8/8/8/8/8/R3K1NR b Kq - 0 1") == {"black_queenside"}


def test_no_castling_legal():
    assert opts("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1") == set()


# --- Rights ---


def test_right_absent_means_illegal():
    assert opts("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1") == set()


def test_stale_right_with_missing_rook():
    # K flag present but no rook on h1: kingside unavailable, rest legal.
    got = opts("r3k2r/8/8/8/8/8/8/R3K3 w KQkq - 0 1")
    assert "white_kingside" not in got
    assert {"white_queenside", "black_kingside", "black_queenside"} <= got


def test_stale_right_with_missing_king_is_safe():
    # No white king at all: no crash, no white options.
    got = opts("r3k2r/8/8/8/8/8/8/R6R w KQkq - 0 1")
    assert got == {"black_kingside", "black_queenside"}


# --- Path ---


def test_kingside_path_blocked():
    got = opts("r3k2r/8/8/8/8/8/8/R3KN1R w KQkq - 0 1")
    assert "white_kingside" not in got
    assert {"white_queenside", "black_kingside", "black_queenside"} <= got


def test_queenside_path_blocked():
    got = opts("r3k2r/8/8/8/8/8/8/R3K2R b Kq - 0 1")
    assert "white_kingside" in got  # sanity: kingside unaffected
    got2 = opts("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1")
    assert "white_queenside" not in got2
    assert "white_kingside" in got2


def test_b_file_occupancy_blocks_queenside():
    # The king never crosses b1, but the rook's path needs it empty.
    assert "white_queenside" not in opts("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1")


# --- King safety ---


def test_king_in_check():
    # Bb4 checks the white king: both white options die, black survives.
    got = opts("r3k2r/8/8/8/1b6/8/8/R3K2R w KQkq - 0 1")
    assert "white_kingside" not in got
    assert "white_queenside" not in got
    assert {"black_kingside", "black_queenside"} <= got


def test_king_crosses_attacked_square():
    # Bc4 hits f1 (transit) but not e1/g1: only kingside dies.
    got = opts("r3k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1")
    assert "white_kingside" not in got
    assert "white_queenside" in got


def test_king_destination_attacked():
    # Nh3 hits g1 (destination) but not e1/f1: only kingside dies.
    got = opts("r3k2r/8/8/8/8/7n/8/R3K2R w KQkq - 0 1")
    assert "white_kingside" not in got
    assert "white_queenside" in got


def test_black_king_safety():
    # White Qd1 hits d8 up the file: black queenside dies, kingside survives.
    board = chess.Board("r3k2r/8/8/8/8/8/8/R2QK2R w KQkq - 0 1")
    assert board.is_attacked_by(chess.WHITE, chess.parse_square("d8")) is True
    assert board.is_attacked_by(chess.WHITE, chess.parse_square("f8")) is False
    probe = board.copy()
    probe.turn = chess.BLACK
    assert chess.Move.from_uci("e8c8") not in probe.legal_moves
    assert chess.Move.from_uci("e8g8") in probe.legal_moves
    assert legal_castling_options("r3k2r/8/8/8/8/8/8/R2QK2R w KQkq - 0 1") == [
        "black_kingside",
        "white_kingside",
    ]


# --- Answer validation ---


def test_validate_exact_partial_wrong():
    answer = {"options": ["white_kingside", "black_queenside"]}
    assert validate(answer, {"options": ["black_queenside", "white_kingside"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"options": ["white_kingside", "white_queenside"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {
        "correct": ["white_kingside"],
        "missed": ["black_queenside"],
        "wrong": ["white_queenside"],
    }
    assert validate(answer, {"options": ["white_queenside"]}).result == AttemptResult.WRONG
    assert validate(answer, {"options": []}).result == AttemptResult.WRONG


def test_validate_order_and_duplicates_do_not_matter():
    answer = {"options": ["white_kingside", "black_queenside"]}
    out = validate(answer, {"options": ["BLACK_QUEENSIDE", "white_kingside", "white_kingside"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {
        "correct": ["black_queenside", "white_kingside"],
        "missed": [],
        "wrong": [],
    }


def test_validate_empty_answer():
    answer = {"options": []}
    ok = validate(answer, {"options": []})
    assert ok.result == AttemptResult.CORRECT
    assert validate(answer, {"options": ["white_kingside"]}).result == AttemptResult.WRONG


def test_validate_malformed_answer_safe():
    answer = {"options": ["white_kingside"]}
    out = validate(answer, {"options": ["white_kingside", "center_castle", 42, None, "O-O"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["white_kingside"]
    assert len(out.detail["wrong"]) == 4
    # Missing/non-list/wrong-typed options never crash.
    assert validate(answer, {}).result == AttemptResult.WRONG
    assert validate(answer, {"options": "white_kingside"}).result == AttemptResult.WRONG
    assert validate(answer, {"options": None}).result == AttemptResult.WRONG


def test_validate_unknown_option_counts_as_wrong():
    answer = {"options": ["white_kingside"]}
    out = validate(answer, {"options": ["white_kingside", "white_center"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["wrong"] == ["white_center"]


def test_validate_ignores_client_side_answer():
    answer = {"options": ["white_kingside"]}
    out = validate(answer, {"options": ["black_kingside"], "squares": ["e1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["white_kingside"]


def test_normalize_option():
    assert normalize_option(" White_Kingside ") == "white_kingside"
    assert normalize_option("e1g1") is None
    assert normalize_option("") is None
    assert normalize_option(None) is None


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call legal_castling_options: they regenerate the four
# candidate moves straight from python-chess legal move generation.


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    expected = []
    for option, color, uci in (
        ("white_kingside", chess.WHITE, "e1g1"),
        ("white_queenside", chess.WHITE, "e1c1"),
        ("black_kingside", chess.BLACK, "e8g8"),
        ("black_queenside", chess.BLACK, "e8c8"),
    ):
        probe = board.copy()
        probe.turn = color
        if chess.Move.from_uci(uci) in probe.legal_moves:
            expected.append(option)
    return sorted(expected)


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
        assert puzzle.answer_json["options"] == expected
        # ...and the validator agrees with the independent recomputation:
        assert puzzle.answer_json["options"] == legal_castling_options(puzzle.fen)
        seen_answers.add(tuple(expected))
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len(seen_answers) >= 8  # varied, not trivially repeated
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
    headers = make_auth_headers(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]

    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"options": puzzle.answer_json["options"]},
            "mode": "practice",
        },
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert sorted(ok.json()["detail"]["correct"]) == sorted(puzzle.answer_json["options"])

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"options": ["no_such_option"]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"options": []}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
