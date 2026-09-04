"""Equal Attackers & Defenders: count rules, validation, seed, API."""

import chess
import pytest

from app.modules.equal_attackers_defenders import seed as seed_mod
from app.modules.equal_attackers_defenders.validator import (
    SLUG,
    balanced_squares,
    counts_for,
    validate,
)
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def bal(fen: str) -> set[str]:
    return set(balanced_squares(fen))


# --- Core count rules ---


def test_one_vs_one_is_target():
    assert bal("4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1") == {"e4"}
    assert counts_for("4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1", "e4") == (1, 1)


def test_two_vs_two_is_target():
    assert bal("4k3/8/8/2b1p3/3N4/2P1P3/8/4K3 w - - 0 1") == {"d4"}


def test_three_vs_three_is_target():
    fen = "3rk3/8/8/2b1p3/3Q4/2P1P3/8/3RK3 w - - 0 1"
    assert "d4" in bal(fen)
    assert counts_for(fen, "d4") == (3, 3)


def test_more_attackers_is_not_target():
    fen = "4k3/8/5n2/8/4P2q/3P4/8/5K2 w - - 0 1"
    assert counts_for(fen, "e4") == (2, 1)
    assert "e4" not in bal(fen)


def test_more_defenders_is_not_target():
    fen = "4k3/4p3/3p4/4P3/3P4/5N2/8/4K3 w - - 0 1"
    assert counts_for(fen, "e5") == (1, 2)
    assert "e5" not in bal(fen)


def test_zero_attackers_is_not_target():
    assert counts_for("4k3/8/8/8/8/2P5/1P6/4K3 w - - 0 1", "c3") == (0, 1)
    assert bal("4k3/8/8/8/8/2P5/1P6/4K3 w - - 0 1") == set()


def test_zero_defenders_is_not_target():
    assert counts_for("4k3/8/8/p7/1P6/8/8/4K3 w - - 0 1", "b4") == (1, 0)
    assert bal("4k3/8/8/p7/1P6/8/8/4K3 w - - 0 1") == set()


# --- Piece types ---


def test_pawn_attacks_are_diagonal_only():
    # e5 push attacks nothing; pawn attack geometry decides, not movement.
    board = chess.Board("4k3/8/4p3/5P2/6P1/8/8/4K3 w - - 0 1")
    e5 = chess.parse_square("e5")
    assert chess.parse_square("e6") not in board.attackers(chess.WHITE, e5)
    assert chess.parse_square("d5") not in board.attackers(chess.WHITE, e5)


def test_knight_bishop_rook_queen_counts():
    assert counts_for("4k3/8/5n2/8/4P3/3P4/8/4K3 w - - 0 1", "e4") == (1, 1)  # knight
    assert counts_for("4k3/8/8/2b1p3/3N4/2P1P3/8/4K3 w - - 0 1", "d4") == (2, 2)  # bishop+pawn
    fen = "3rk3/8/8/2b1p3/3Q4/2P1P3/8/3RK3 w - - 0 1"
    assert counts_for(fen, "d8") == (1, 1)  # rook file vs king
    assert counts_for("4k3/8/5q2/8/3N4/2P5/8/4K3 w - - 0 1", "d4") == (1, 1)  # queen


def test_king_attack_and_defense():
    fen = "4k3/8/8/8/1N6/3k4/2P5/4K3 w - - 0 1"
    assert counts_for(fen, "c2") == (1, 1)  # Kd3 attacks, Nb4 defends
    assert "c2" in bal(fen)


# --- Blockers ---


def test_blocked_attacker_does_not_count():
    # Qh4 eyes e4 but Ng4 blocks the rank: e4 has no attackers at all.
    board = chess.Board("4k3/8/8/8/4P1Nq/8/8/5K2 w - - 0 1")
    e4 = chess.parse_square("e4")
    assert chess.parse_square("h4") not in board.attackers(chess.BLACK, e4)
    assert bal("4k3/8/8/8/4P1Nq/8/8/5K2 w - - 0 1") == set()


def test_blocked_defender_does_not_count():
    # Rd1 would defend d4, but Pd2 blocks the file: 2 attackers vs 1 defender.
    fen = "3rk3/8/8/2b5/3Q4/2P5/3P4/4K3 w - - 0 1"
    assert counts_for(fen, "d4") == (2, 1)
    assert "d4" not in bal(fen)


def test_piece_behind_blocker_does_not_count():
    board = chess.Board("4k3/8/4p3/1p1P4/2B5/8/8/4K3 w - - 0 1")
    e6 = chess.parse_square("e6")
    assert chess.parse_square("c4") not in board.attackers(chess.WHITE, e6)


# --- Self-defense ---


def test_piece_itself_is_not_a_defender():
    board = chess.Board("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        assert sq not in board.attackers(piece.color, sq)
    # ...and the validator subtracts it defensively anyway:
    assert counts_for("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1", "e4") == (0, 0)


def test_counts_for_rejects_empty_square_and_bad_fen():
    with pytest.raises(ValueError):
        counts_for("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1", "e5")
    with pytest.raises(ValueError):
        balanced_squares("not-a-fen")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Validation ---


def test_validate_exact_partial_wrong():
    answer = {"squares": ["d4", "d8"]}
    assert validate(answer, {"selected_squares": ["d8", "d4"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["d4", "a1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["d4"], "missed": ["d8"], "wrong": ["a1"]}
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG


def test_validate_order_and_duplicates_do_not_matter():
    answer = {"squares": ["d4", "d8"]}
    out = validate(answer, {"selected_squares": ["d8", "d4", "d4", "D8"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["d4", "d8"], "missed": [], "wrong": []}


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


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    targets = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        attackers = board.attackers(not piece.color, sq)
        if not attackers:
            continue
        if len(attackers) == len(board.attackers(piece.color, sq) - {sq}):
            targets.append(chess.square_name(sq))
    return sorted(targets)


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
        # ...and the validator agrees with the independent recomputation:
        assert puzzle.answer_json["squares"] == balanced_squares(puzzle.fen)
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
