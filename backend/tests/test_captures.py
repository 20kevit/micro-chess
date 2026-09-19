"""Captures: capture rules per piece, validation, seed, API."""

import chess
import pytest

from app.modules.captures import seed as seed_mod
from app.modules.captures.validator import SLUG, capturable_squares, validate
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers


def caps(fen: str, hunter: str) -> set[str]:
    return set(capturable_squares(fen, hunter))


# --- Basic cases ---


def test_single_capture():
    assert caps("4k2n/8/8/3p4/2B5/8/8/4K3 w - - 0 1", "c4") == {"d5"}


def test_multiple_captures():
    assert caps("4k3/8/2p1p3/1P6/3N4/8/8/4K3 w - - 0 1", "d4") == {"c6", "e6"}
    # Only captures count: quiet rook moves along rank/file are excluded.
    assert caps("2r1k3/8/8/3p4/3R2p1/8/8/4K3 w - - 0 1", "d4") == {"d5", "g4"}


def test_no_captures():
    assert caps("r3k3/8/3p4/8/4P3/8/8/4K3 w - - 0 1", "e4") == set()


# --- Sliding pieces ---


def test_friendly_blocker_shields_enemy_behind():
    got = caps("4k3/8/4p3/1p1P4/2B5/8/8/4K3 w - - 0 1", "c4")
    assert got == {"b5"}  # e6 is hidden behind friendly d5


def test_enemy_behind_first_enemy_not_capturable():
    got = caps("4k3/8/3p4/3p4/3R4/8/8/4K3 w - - 0 1", "d4")
    assert "d5" in got
    assert "d6" not in got


def test_queen_corner_blocked_behind_capture():
    got = caps("4k3/8/8/8/5p2/8/5pp1/3K1Q2 w - - 0 1", "f1")
    assert got == {"f2", "g2"}  # f4 is hidden behind f2


# --- Pieces ---


def test_pawn_diagonal_only():
    got = caps("4k3/8/8/3p1p2/4P3/8/8/4K3 w - - 0 1", "e4")
    assert got == {"d5", "f5"}  # e5 push is not a capture


def test_pawn_no_diagonal_capture():
    assert caps("r3k3/8/3p4/8/4P3/8/8/4K3 w - - 0 1", "e4") == set()


def test_knight_jumps_and_ignores_friendly_block():
    got = caps("4k3/8/8/8/8/1p6/2P5/N3K3 w - - 0 1", "a1")
    assert got == {"b3"}  # c2 is friendly


def test_bishop_two_rays():
    assert caps("4k3/8/8/8/8/p3p3/8/2B1K3 w - - 0 1", "c1") == {"a3", "e3"}


def test_rook_corner():
    assert caps("4k3/8/8/p7/8/8/7p/R3K3 w - - 0 1", "a1") == {"a5"}


def test_queen_two_captures():
    assert caps("4k3/8/8/3pp3/3Q4/8/8/4K3 w - - 0 1", "d4") == {"d5", "e5"}


# --- King safety ---


def test_king_legal_capture():
    assert caps("4k3/7p/8/3p4/4K3/8/8/8 w - - 0 1", "e4") == {"d5"}


def test_king_illegal_capture_onto_attacked_square():
    # d5 is defended by the c6 pawn, so the king cannot capture there.
    assert caps("4k3/8/2p5/3p4/4K3/8/8/8 w - - 0 1", "e4") == set()


def test_empty_hunter_square_rejected():
    with pytest.raises(ValueError):
        capturable_squares("4k3/8/8/3p4/2B5/8/8/4K3 w - - 0 1", "e4")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Validation ---


def test_validate_correct_partial_wrong():
    answer = {"squares": ["d5", "e6"], "from": "d4"}
    assert validate(answer, {"selected_squares": ["d5", "e6"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["d5", "a1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["d5"], "missed": ["e6"], "wrong": ["a1"]}
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG
    malformed = validate(answer, {"selected_squares": ["d5", "e6", "zzz"]})
    assert malformed.result == AttemptResult.PARTIAL
    assert "zzz" in malformed.detail["wrong"]


def test_validate_empty_answer():
    answer = {"squares": [], "from": "e4"}
    ok = validate(answer, {"selected_squares": []})
    assert ok.result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["d5"]}).result == AttemptResult.WRONG


def test_validate_ignores_client_side_answer():
    answer = {"squares": ["d5"], "from": "c4"}
    out = validate(answer, {"selected_squares": ["a1"], "squares": ["a1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["d5"]


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str, hunter: str) -> list[str]:
    board = chess.Board(fen)
    origin = chess.parse_square(hunter)
    return sorted(
        chess.square_name(m.to_square)
        for m in board.legal_moves
        if m.from_square == origin and board.is_capture(m)
    )


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    kinds = set()
    empty_count = 0
    for puzzle in puzzles:
        assert puzzle.fen
        hunter = puzzle.position_json["from"]
        expected = _independent(puzzle.fen, hunter)
        assert puzzle.answer_json["squares"] == expected
        if not expected:
            empty_count += 1
        kinds.add(chess.Board(puzzle.fen).piece_at(chess.parse_square(hunter)).symbol().lower())
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert kinds == {"p", "n", "b", "r", "q"}
    assert empty_count >= 1  # "no captures" cases are covered
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
    assert body[0]["position_json"]["from"]

    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "practice",
        },
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    # Per-square scorer (registered for the slug): 2 targets x +5.
    assert ok.json()["score"] == 10.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": ["h1"]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] in ("wrong", "partial")

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401
