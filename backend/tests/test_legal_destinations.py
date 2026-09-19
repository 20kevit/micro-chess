"""Legal Destinations: movement rules, profiles, validation, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.legal_destinations import seed as seed_mod
from app.modules.legal_destinations.validator import (
    IGNORE_ENEMY_ATTACKS,
    SLUG,
    STANDARD,
    legal_destinations,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers


def dests(fen: str, origin: str, profile: str = STANDARD) -> set[str]:
    return set(legal_destinations(fen, origin, profile))


# --- Movement rules (computed independently against python-chess) ---


def test_knight_center_has_eight():
    assert dests("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1", "d4") == {
        "b3", "b5", "c2", "c6", "e2", "e6", "f3", "f5",
    }


def test_knight_corner_has_three():
    assert dests("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1", "b1") == {"a3", "c3", "d2"}


def test_bishop_blockers_and_capture():
    got = dests("4k3/8/8/3p4/2B5/8/3P4/4K3 w - - 0 1", "c4")
    assert "d5" in got  # enemy capture allowed
    assert "e6" not in got  # ray stops behind the capture
    assert "d3" in got and "e2" in got and "f1" in got  # open diagonal
    assert "b5" in got and "a6" in got
    assert "b3" in got and "a2" in got


def test_rook_blockers_and_capture():
    got = dests("4k3/8/8/3p4/3R4/8/8/4K3 w - - 0 1", "d4")
    assert got == {"d5", "d3", "d2", "d1", "a4", "b4", "c4", "e4", "f4", "g4", "h4"}


def test_queen_center_count():
    assert len(dests("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1", "d4")) == 27


def test_pawn_double_from_start():
    assert dests("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2") == {"e3", "e4"}


def test_pawn_blocked_single_but_captures():
    # e4 blocked-empty ahead; captures only on occupied diagonals.
    assert dests("4k3/8/8/3p1p2/4P3/8/8/4K3 w - - 0 1", "e4") == {"d5", "e5", "f5"}


def test_pawn_no_empty_diagonal_destination():
    got = dests("4k3/8/8/8/3p4/4P3/8/4K3 w - - 0 1", "e3")
    assert got == {"d4", "e4"}
    assert "f4" not in got  # empty diagonal is not a pawn move


def test_king_cannot_move_into_check():
    got = dests("4k3/4r3/8/8/8/8/8/4K3 w - - 0 1", "e1")
    assert got == {"d1", "d2", "f1", "f2"}
    assert "e2" not in got  # attacked by the rook


def test_king_cannot_capture_protected_piece():
    # Rd2 is defended by Kc3; every other neighbor is under attack.
    assert dests("8/8/8/8/8/2k5/3r4/4K3 w - - 0 1", "e1") == {"f1"}


def test_ignore_enemy_attacks_allows_checked_squares():
    fen = "4k3/4r3/8/8/8/8/8/4K3 w - - 0 1"
    assert dests(fen, "e1", IGNORE_ENEMY_ATTACKS) == {"d1", "d2", "e2", "f1", "f2"}
    assert "e2" not in dests(fen, "e1", STANDARD)


def test_unknown_profile_rejected():
    with pytest.raises(ValueError):
        legal_destinations("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1", "d4", "nope")


def test_empty_target_square_rejected():
    with pytest.raises(ValueError):
        legal_destinations("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1", "e4")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Validation against the authoritative stored answer ---


def test_validate_correct_partial_wrong():
    answer = {"squares": ["d5", "e6"], "from": "c4", "profile": STANDARD}
    assert validate(answer, {"selected_squares": ["d5", "e6"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["d5"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["d5"], "missed": ["e6"], "wrong": []}
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG
    malformed = validate(answer, {"selected_squares": ["d5", "zzz"]})
    assert malformed.result == AttemptResult.PARTIAL
    assert "zzz" in malformed.detail["wrong"]


def test_validate_ignores_client_side_answer():
    # A client-provided destination list must not influence the verdict.
    answer = {"squares": ["d5"], "from": "c4", "profile": STANDARD}
    attempt = {"selected_squares": ["a1"], "squares": ["a1"]}
    out = validate(answer, attempt)
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["d5"]


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str, origin: str, profile: str) -> list[str]:
    board = chess.Board(fen)
    origin_sq = chess.parse_square(origin)
    if profile == STANDARD:
        moves = board.legal_moves
    else:
        moves = board.pseudo_legal_moves
    return sorted(chess.square_name(m.to_square) for m in moves if m.from_square == origin_sq)


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    kinds = set()
    for puzzle in puzzles:
        assert puzzle.fen
        target = puzzle.position_json["from"]
        profile = puzzle.position_json["profile"]
        expected = _independent(puzzle.fen, target, profile)
        assert expected, f"puzzle {puzzle.id} has empty answer"
        assert puzzle.answer_json["squares"] == expected
        kinds.add(chess.Board(puzzle.fen).piece_at(chess.parse_square(target)).symbol().lower())
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert kinds == {"p", "n", "b", "r", "q", "k"}
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
    # Per-square scoring: +5 per correct destination (Exercise 1 philosophy).
    assert ok.json()["score"] == 5.0 * len(puzzle.answer_json["squares"])

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401
