"""Trapped Pieces: pseudo-legal classification, validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from app.modules.trapped_pieces import seed as seed_mod
from app.modules.trapped_pieces.validator import SLUG, trapped_squares, validate


def trapped(fen: str) -> set[str]:
    return set(trapped_squares(fen))


# --- Basic trapped cases ---


def test_knight_corner_trapped():
    assert trapped("4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1") == {"a1"}


def test_bishop_trapped_by_own_pawns():
    assert trapped("2b1k3/1p1p4/8/8/8/8/8/4K3 w - - 0 1") == {"c8"}


def test_rook_corner_trapped():
    assert trapped("4k3/8/8/8/8/8/P7/RN4K1 w - - 0 1") == {"a1"}


def test_queen_trapped():
    assert trapped("4k3/8/8/8/8/8/2PPP3/2BQK3 w - - 0 1") == {"d1"}


def test_bishop_c1_trapped():
    assert trapped("4k3/8/8/8/8/8/1P1P4/2B1K3 w - - 0 1") == {"c1"}


def test_rook_h1_trapped():
    assert trapped("4k3/8/8/8/8/8/6PP/6KR w - - 0 1") == {"h1"}


def test_double_trapped():
    assert trapped("2bqk3/1pppp3/8/8/8/8/8/4K3 w - - 0 1") == {"c8", "d8"}


def test_two_corners_trapped():
    assert trapped("2b1k3/1p1p4/8/8/8/8/P7/RN4K1 w - - 0 1") == {"a1", "c8"}


# --- Pawns ---


def test_pawns_mutually_blocked():
    assert trapped("4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1") == {"e3", "e4"}


def test_pawns_d_file_blocked():
    assert trapped("4k3/8/8/8/3p4/3P4/8/4K3 w - - 0 1") == {"d3", "d4"}


def test_pawn_with_push_not_trapped():
    assert trapped("4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1") == set()


def test_pawn_promotion_move_not_trapped():
    assert trapped("4k3/P7/8/8/8/8/8/4K3 w - - 0 1") == set()


def test_knight_capture_means_not_trapped():
    # Knight h1 captures g3, so nothing is trapped.
    assert trapped("4k3/8/8/8/8/6p1/5PK1/7N w - - 0 1") == set()


def test_knight_h8_and_pawn_trapped():
    assert trapped("4k2n/5pp1/6p1/8/8/8/8/4K3 w - - 0 1") == {"g7", "h8"}


# --- Pinned vs trapped, kings ---


def test_pinned_knight_not_trapped():
    # Knight e2 is pinned to the king by rook e8: pseudo moves exist,
    # so it is NOT trapped even though it has zero legal moves.
    fen = "4rk2/8/8/8/8/8/4N3/4K3 w - - 0 1"
    assert trapped(fen) == set()
    board = chess.Board(fen)
    board.turn = chess.WHITE
    mask = chess.BB_SQUARES[chess.E2]
    assert any(True for _ in board.generate_pseudo_legal_moves(from_mask=mask))
    assert not any(m.from_square == chess.E2 for m in board.legal_moves)


def test_kings_never_trapped():
    # White king g1 has zero pseudo-legal moves here but must be excluded.
    fen = "4k3/8/8/8/8/8/5PPP/5RKB w - - 0 1"
    got = trapped(fen)
    assert "g1" not in got
    assert got == {"h1"}


def test_free_position_empty():
    assert trapped("4k3/8/8/8/8/8/1PPPPP2/RN2K2R w K - 0 1") == set()


def test_invalid_fen_raises():
    with pytest.raises(ValueError):
        trapped_squares("not-a-fen")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Validation ---


def test_validate_correct_partial_wrong():
    answer = {"squares": ["a1", "c8"]}
    assert validate(answer, {"selected_squares": ["a1", "c8"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["a1", "h1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["a1"], "missed": ["c8"], "wrong": ["h1"]}
    assert validate(answer, {"selected_squares": ["h1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG
    malformed = validate(answer, {"selected_squares": ["a1", "c8", "zzz"]})
    assert malformed.result == AttemptResult.PARTIAL
    assert "zzz" in malformed.detail["wrong"]


def test_validate_empty_answer():
    answer = {"squares": []}
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": ["zzz"]}).result == AttemptResult.WRONG


def test_validate_case_insensitive_and_ignores_client_answer():
    answer = {"squares": ["a1"]}
    assert validate(answer, {"selected_squares": ["A1"]}).result == AttemptResult.CORRECT
    out = validate(answer, {"selected_squares": ["h1"], "squares": ["h1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["a1"]


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    found: list[str] = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        board.turn = piece.color
        mask = chess.BB_SQUARES[sq]
        if not any(True for _ in board.generate_pseudo_legal_moves(from_mask=mask)):
            found.append(chess.square_name(sq))
    return sorted(found)


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    kinds = set()
    empty_count = 0
    for puzzle in puzzles:
        assert puzzle.fen
        expected = _independent(puzzle.fen)
        assert puzzle.answer_json["squares"] == expected
        for sq in expected:
            kinds.add(chess.Board(puzzle.fen).piece_at(chess.parse_square(sq)).symbol().lower())
        if not expected:
            empty_count += 1
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        assert puzzle.position_json["mode"] == "standard"
    assert {"p", "n", "b", "r", "q"} <= kinds
    assert empty_count >= 1
    assert len({p.initial_rating for p in puzzles}) >= 5


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    assert body[0]["position_json"]["mode"] == "standard"

    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "practice",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": ["h1"]}, "mode": "practice"},
    )
    assert bad.json()["result"] in ("wrong", "partial")

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401
