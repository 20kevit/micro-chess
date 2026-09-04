"""Hanging Pieces: attack/defense rules, validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.hanging_pieces import seed as seed_mod
from app.modules.hanging_pieces.validator import SLUG, hanging_squares, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def hang(fen: str) -> set[str]:
    return set(hanging_squares(fen))


# --- Basic ---


def test_one_hanging_piece():
    assert hang("4k3/8/2b5/8/4N3/8/8/4K3 w - - 0 1") == {"e4"}


def test_multiple_hanging_pieces():
    assert hang("4k3/8/5n2/2b5/3PP3/8/8/4K3 w - - 0 1") == {"c5", "d4", "e4"}


def test_no_hanging_pieces():
    assert hang("4k3/8/8/8/8/5N2/5P2/4K3 w - - 0 1") == set()


# --- Attack/defense ---


def test_attacked_and_defended_is_not_hanging():
    assert hang("4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1") == set()


def test_multiple_attackers_no_defenders_is_hanging():
    assert hang("4k3/8/2n1n3/8/3P4/8/8/4K3 w - - 0 1") == {"d4"}


def test_multiple_attackers_and_defenders_is_not_hanging():
    assert hang("4k3/8/8/2b1p3/3N4/2P1P3/8/4K3 w - - 0 1") == set()


# --- Piece types ---


def test_pawn_attacks_are_diagonal_only():
    # f5 attacks e6 (hanging) but the e5 push attacks nothing.
    got = hang("4k3/8/4p3/5P2/6P1/8/8/4K3 w - - 0 1")
    assert got == {"e6"}


def test_knight_attack_and_defense():
    # Nd4 is attacked by Bf6 but defended by Pc3; pe6 is undefended.
    assert hang("4k3/8/4pb2/5P2/3N4/2P5/8/4K3 w - - 0 1") == {"e6"}


def test_bishop_rook_queen_line_attacks():
    assert hang("3rk3/8/8/8/8/8/5K2/3R4 w - - 0 1") == {"d1"}
    assert hang("4k3/8/8/8/8/p3p3/8/2B1K3 w - - 0 1") == {"a3", "e3"}
    # f2/g2 hang on the queen's lines; f1 hangs on the g2 pawn's attack.
    assert hang("4k3/8/8/8/5p2/8/5pp1/3K1Q2 w - - 0 1") == {"f1", "f2", "g2"}


def test_king_as_attacker():
    # Kd3 attacks Pc2; Pc2 attacks Kd3 back; neither is defended.
    assert hang("4k3/8/8/8/8/3k4/2P5/4K3 w - - 0 1") == {"c2", "d3"}


def test_king_as_defender():
    # Pc2 is attacked by Bb3 but defended by Kd1; Bb3 itself is hanging.
    assert hang("4k3/8/8/8/8/1b6/2P5/3K4 w - - 0 1") == {"b3"}


# --- Blockers ---


def test_sliding_attack_blocked():
    # Bc4 cannot see through friendly Pd5: e6 is attacked by the pawn, not the bishop.
    board = chess.Board("4k3/8/4p3/1p1P4/2B5/8/8/4K3 w - - 0 1")
    e6 = chess.parse_square("e6")
    assert chess.parse_square("c4") not in board.attackers(chess.WHITE, e6)
    assert hang("4k3/8/4p3/1p1P4/2B5/8/8/4K3 w - - 0 1") == {"b5", "c4", "e6"}


def test_defender_blocked():
    # pd2 blocks the queen's defense of Nd4; both d2 and d4 hang.
    assert hang("4k3/8/8/2b5/3N4/8/3p4/3Q1K2 w - - 0 1") == {"d2", "d4"}


def test_piece_behind_blocker_not_attacked():
    # d6 hides behind the d5 pawn from the d4 rook... via attackers API:
    # a rook on d4 does not attack d6 through d5.
    board = chess.Board("4k3/8/3p4/3p4/3R4/8/8/4K3 w - - 0 1")
    d6 = chess.parse_square("d6")
    assert chess.parse_square("d4") not in board.attackers(chess.WHITE, d6)


def test_piece_never_counts_itself_as_defender():
    # Lone kings facing no attack: no square lists itself as a defender.
    board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        assert sq not in board.attackers(piece.color, sq)


# --- Validation ---


def test_validate_exact_partial_wrong():
    answer = {"squares": ["d4", "e4"]}
    assert validate(answer, {"selected_squares": ["e4", "d4"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["d4", "a1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["d4"], "missed": ["e4"], "wrong": ["a1"]}
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG


def test_validate_order_and_duplicates_do_not_matter():
    answer = {"squares": ["d4", "e4"]}
    out = validate(answer, {"selected_squares": ["e4", "d4", "d4", "E4"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["d4", "e4"], "missed": [], "wrong": []}


def test_validate_malformed_answer_safe():
    answer = {"squares": ["d4"]}
    out = validate(answer, {"selected_squares": ["d4", "zzz", 42, None]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["d4"]
    assert len(out.detail["wrong"]) == 3


def test_validate_empty_answer():
    answer = {"squares": []}
    ok = validate(answer, {"selected_squares": []})
    assert ok.result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["d4"]}).result == AttemptResult.WRONG


def test_validate_ignores_client_side_answer():
    answer = {"squares": ["d4"]}
    out = validate(answer, {"selected_squares": ["a1"], "squares": ["a1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["d4"]


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    hanging = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        if not board.attackers(not piece.color, sq):
            continue
        if board.attackers(piece.color, sq) - {sq}:
            continue
        hanging.append(chess.square_name(sq))
    return sorted(hanging)


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
        assert puzzle.answer_json["squares"] == expected
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
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]

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
    assert sorted(ok.json()["detail"]["correct"]) == sorted(puzzle.answer_json["squares"])

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": ["h1"]}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
