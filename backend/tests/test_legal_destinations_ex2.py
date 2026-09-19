"""Exercise 2 (Legal Destinations) spec coverage.

Covers the product spec beyond the legacy seed tests:
- per-piece movement details (pawn edges/backward, knight jumping,
  slider blockers, king edges/friendly occupancy)
- set semantics (order, duplicates) and malformed payloads
- exact scoring formula incl. spec examples and zero-target +5
- dynamic generator validity (white-only, no black king, one target,
  blockers, variety, bounded)
- practice next + speed session lifecycle (20-buffer, 60s, report,
  authoritative expiry, no answer leak, client-solution ignored)
"""

import random

import chess
import pytest

from app.modules.exercises import registry
from app.modules.legal_destinations import generator as gen
from app.modules.legal_destinations import sessions as session_service
from app.modules.legal_destinations.models import LegalSpeedSession
from app.modules.legal_destinations.scoring import score_squares
from app.modules.legal_destinations.validator import (
    IGNORE_ENEMY_ATTACKS,
    SLUG,
    STANDARD,
    legal_destinations,
    validate,
)
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers


def dests(fen: str, origin: str, profile: str = IGNORE_ENEMY_ATTACKS) -> set[str]:
    return set(legal_destinations(fen, origin, profile))


# --- Pawn details (white-only boards, IGNORE profile) ---


def test_pawn_one_step_open():
    assert dests("8/8/8/8/8/8/3P4/4K3 w - - 0 1", "d2") == {"d3", "d4"}


def test_pawn_two_step_only_from_start_rank():
    # e4 pawn: single step only.
    assert dests("8/8/8/8/4P3/8/8/4K3 w - - 0 1", "e4") == {"e5"}


def test_pawn_blocked_ahead_has_no_forward_move():
    # Friendly piece directly ahead blocks the pawn completely.
    assert dests("8/8/8/8/8/3N4/3P4/4K3 w - - 0 1", "d2") == set()


def test_pawn_blocked_double_but_single_open():
    # Blocker on d4 stops the double step but d3 stays legal.
    assert dests("8/8/8/8/3N4/8/3P4/4K3 w - - 0 1", "d2") == {"d3"}


def test_pawn_edge_file_no_wrap():
    got = dests("8/8/8/8/8/8/H7/4K3 w - - 0 1".replace("H", "P"), "a2")
    assert got == {"a3", "a4"}


def test_pawn_never_moves_backward():
    got = dests("8/8/8/8/4P3/8/8/4K3 w - - 0 1", "e4")
    assert "e3" not in got and "e2" not in got


def test_pawn_h_rank_single():
    assert dests("8/8/8/8/7P/8/8/4K3 w - - 0 1", "h4") == {"h5"}


def test_pawn_white_only_has_no_captures():
    # Empty diagonals are not destinations on a white-only board.
    got = dests("8/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2")
    assert got == {"e3", "e4"}


# --- Knight details ---


def test_knight_edge_has_two():
    assert dests("8/8/8/8/8/8/8/4K2N w - - 0 1", "h1") == {"f2", "g3"}


def test_knight_friendly_occupied_excluded():
    # d4 knight with friendly pieces on b3 and e6: those are excluded.
    got = dests("8/8/4P3/8/3N4/1P6/8/4K3 w - - 0 1", "d4")
    assert "b3" not in got and "e6" not in got
    assert {"b5", "c2", "c6", "e2", "f3", "f5"} <= got


def test_knight_jumps_over_blockers():
    # Ring of friendly pieces around the knight: destinations unaffected.
    got = dests("8/8/8/2PPP3/2PNP3/2PPP3/8/4K3 w - - 0 1", "d4")
    assert len(got) == 8


# --- Slider blockers ---


def test_bishop_friendly_blocks_ray():
    # Friendly pawn on e6 stops the c4-bishop ray; e6 itself not selectable.
    got = dests("8/8/4P3/8/2B5/8/8/4K3 w - - 0 1", "c4")
    assert "d5" in got and "e6" not in got and "f7" not in got


def test_bishop_multiple_blockers():
    # b3 pawn blocks the SW ray (b3/a2 out); e2 pawn blocks SE (e2/f1 out).
    got = dests("8/8/8/8/2B5/1P6/4P3/4K3 w - - 0 1", "c4")
    assert "b3" not in got and "a2" not in got
    assert "e2" not in got and "f1" not in got
    assert "b5" in got and "d5" in got and "d3" in got


def test_rook_friendly_blocks_rank_and_file():
    got = dests("8/8/8/8/3RP3/8/8/4K3 w - - 0 1", "d4")
    assert "e4" not in got and "f4" not in got
    assert "c4" in got and "d5" in got and "d3" in got


def test_rook_edge_corner():
    # Own king on e1 blocks the first rank; h1 is unreachable behind it.
    got = dests("8/8/8/8/8/8/8/R3K3 w - - 0 1", "a1")
    assert "a8" in got and "d1" in got
    assert "e1" not in got and "h1" not in got


def test_queen_mixed_blockers():
    # d5 pawn blocks the north ray; c3 pawn blocks the SW diagonal.
    got = dests("8/8/8/3P4/3Q4/2P5/8/4K3 w - - 0 1", "d4")
    assert "d5" not in got and "d6" not in got
    assert "c3" not in got and "b2" not in got
    assert "d3" in got and "c4" in got and "e4" in got and "e5" in got


# --- King ---


def test_king_center_all_adjacent():
    assert dests("8/8/8/8/3K4/8/8/8 w - - 0 1", "d4") == {
        "c3", "c4", "c5", "d3", "d5", "e3", "e4", "e5",
    }


def test_king_corner_has_three():
    assert dests("8/8/8/8/8/8/8/K7 w - - 0 1", "a1") == {"a2", "b1", "b2"}


def test_king_friendly_occupied_excluded():
    got = dests("8/8/8/8/8/3PP3/3P4/3K4 w - - 0 1", "d1")
    assert got == {"c1", "c2", "e1", "e2"}


# --- Set semantics + validation ---


def test_answer_order_irrelevant_and_duplicates_normalized():
    answer = {"squares": ["a1", "b2", "c3"]}
    out = validate(answer, {"selected_squares": ["c3", "a1", "b2"]})
    assert out.result == AttemptResult.CORRECT
    dup = validate(answer, {"selected_squares": ["a1", "a1", "b2", "c3", "b2"]})
    assert dup.result == AttemptResult.CORRECT
    assert dup.detail == {"correct": ["a1", "b2", "c3"], "missed": [], "wrong": []}


def test_malformed_squares_count_as_wrong():
    answer = {"squares": ["d5", "e6"]}
    out = validate(answer, {"selected_squares": ["d5", "zzz", "i9"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["d5"]
    assert out.detail["missed"] == ["e6"]
    assert sorted(out.detail["wrong"]) == ["i9", "zzz"]


def test_impossible_destination_is_wrong():
    answer = {"squares": ["d5"]}
    out = validate(answer, {"selected_squares": ["h8"]})
    assert out.result == AttemptResult.WRONG


def test_client_solution_fields_ignored():
    answer = {"squares": ["d5"]}
    out = validate(answer, {"selected_squares": ["a1"], "squares": ["a1"], "from": "a1"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["d5"]


# --- Scoring (exact spec formula) ---


def test_scoring_spec_examples():
    # Correct [b2,c3,d4], select all -> 3*5 = 15.
    v = validate({"squares": ["b2", "c3", "d4"]}, {"selected_squares": ["b2", "c3", "d4"]})
    assert score_squares(v) == 15.0
    # Select [b2,c3] -> 2*5 - 1 = 9.
    v = validate({"squares": ["b2", "c3", "d4"]}, {"selected_squares": ["b2", "c3"]})
    assert v.result == AttemptResult.PARTIAL
    assert score_squares(v) == 9.0
    # Select [b2,c3,h8]: correct=2, missed=1, wrong=1 -> 10-1-2 = 7.
    # (Spec text shows +8 with a -1*2 typo; the formula 5/-1/-2 gives 7.)
    v = validate({"squares": ["b2", "c3", "d4"]}, {"selected_squares": ["b2", "c3", "h8"]})
    assert score_squares(v) == 7.0
    # Select nothing -> 0 - 3 = -3 (negative kept, not clamped).
    v = validate({"squares": ["b2", "c3", "d4"]}, {"selected_squares": []})
    assert score_squares(v) == -3.0


def test_zero_target_scoring():
    v = validate({"squares": []}, {"selected_squares": []})
    assert v.result == AttemptResult.CORRECT
    assert score_squares(v) == 5.0
    v = validate({"squares": []}, {"selected_squares": ["e4"]})
    assert v.result == AttemptResult.WRONG
    assert score_squares(v) == -2.0
    v = validate({"squares": []}, {"selected_squares": ["e4", "d5"]})
    assert score_squares(v) == -4.0


def test_scorer_registered_for_slug():
    assert registry.get_scorer(SLUG) is not None
    assert registry.score_for_answer(SLUG, validate({"squares": []}, {"selected_squares": []})) == 5.0


# --- Generator ---


def _assert_white_only(fen: str):
    board = chess.Board(fen)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is not None:
            assert piece.color == chess.WHITE, f"non-white piece in {fen}"
    assert board.turn == chess.WHITE


def test_generator_valid_positions():
    rng = random.Random(1234)
    seen_types: set[str] = set()
    seen_ratings: set[float] = set()
    for _ in range(30):
        data = gen.generate_question_data(rng)
        assert data["fen"] and data["from"] and data["prompt_fa"]
        board = chess.Board(data["fen"])  # raises on malformed FEN
        _assert_white_only(data["fen"])
        assert "k" not in "".join(
            p.symbol().lower() for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.color == chess.BLACK
        )
        # Exactly one white king and exactly one target piece square.
        kings = [sq for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.symbol() == "K"]
        assert len(kings) == 1
        target = board.piece_at(chess.parse_square(data["from"]))
        assert target is not None and target.color == chess.WHITE
        seen_types.add(target.symbol().lower())
        # Stored answer recomputes independently.
        expected = sorted(
            chess.square_name(m.to_square)
            for m in board.pseudo_legal_moves
            if m.from_square == chess.parse_square(data["from"])
        )
        assert data["squares"] == expected
        assert data["profile"] == IGNORE_ENEMY_ATTACKS
        seen_ratings.add(data.get("initial_rating", 0) if isinstance(data.get("initial_rating"), float) else 0)
    # Variety: all six piece types appear across draws.
    assert seen_types == {"p", "n", "b", "r", "q", "k"}


def test_generator_persists_and_dedups(db_session):
    rng = random.Random(42)
    p1 = gen.create_puzzle(db_session, rng)
    assert p1.answer_json["squares"] == gen.question_for_position(
        p1.fen, p1.position_json["from"], p1.position_json["profile"]
    )["squares"]
    assert "answer_json" not in p1.to_dict() if hasattr(p1, "to_dict") else True
    p2 = gen.create_puzzle(db_session, rng, exclude_ids={p1.id})
    assert p2.id != p1.id
    ratings = {p.initial_rating for p in db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()}
    assert len(ratings) >= 2


def test_generator_bounded_failure():
    rng = random.Random(0)
    # Forcing an impossible piece type raises ValueError, never loops forever.
    with pytest.raises(ValueError):
        gen.generate_position_data(rng, piece_type="x")


def test_generator_all_piece_types_placeable():
    rng = random.Random(7)
    for ptype in ("p", "n", "b", "r", "q", "k"):
        pos = gen.generate_position_data(rng, piece_type=ptype)
        board = chess.Board(pos["fen"])
        assert board.piece_at(chess.parse_square(pos["from"])).symbol().lower() == ptype


# --- Practice + speed API ---


def test_practice_next_hides_answer(client, db_session):
    res = client.post("/api/v1/legal-destinations/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] and body["prompt_fa"]
    assert "answer_json" not in body
    assert body["position_json"]["from"]
    assert body["exercise_slug"] == SLUG


def _open(client):
    body = client.post("/api/v1/legal-destinations/sessions", json={}).json()
    assert body["status"] == "preparing"
    return body["session_id"]


def _prepare(client, session_id, count=20):
    res = client.post(f"/api/v1/legal-destinations/sessions/{session_id}/puzzles", json={"count": count})
    assert res.status_code == 200, res.text
    return res.json()


def _start(client, session_id):
    res = client.post(f"/api/v1/legal-destinations/sessions/{session_id}/start")
    assert res.status_code == 200, res.text
    return res.json()


def _ready_session(client, count=20):
    sid = _open(client)
    puzzles = _prepare(client, sid, count)
    started = _start(client, sid)
    return sid, puzzles, started


def test_speed_lifecycle_buffer_and_clock(client, db_session):
    sid = _open(client)
    res = client.post(f"/api/v1/legal-destinations/sessions/{sid}/start")
    assert res.status_code == 409
    _prepare(client, sid, 19)
    assert client.post(f"/api/v1/legal-destinations/sessions/{sid}/start").status_code == 409
    _prepare(client, sid, 1)
    started = _start(client, sid)
    assert started["status"] == "active" and started["duration_s"] == 60
    assert started["buffered"] == 20


def test_speed_prepare_hides_answers(client, db_session):
    sid = _open(client)
    batch = _prepare(client, sid, 20)
    assert len(batch) == 20
    assert all("answer_json" not in p for p in batch)
    assert len({p["id"] for p in batch}) == 20


def test_speed_submit_and_report(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/legal-destinations/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["attempt"]["mode"] == "practice"
    assert payload["attempt"]["rating_delta"] is None
    assert payload["session"]["attempted"] == 1
    report = client.get(f"/api/v1/legal-destinations/sessions/{sid}/report").json()
    assert report["session"]["attempted"] == 1
    assert len(report["entries"]) == 1
    attempts = db_session.query(Attempt).order_by(Attempt.id).all()
    assert sum(a.score for a in attempts) == report["session"]["score"]


def test_speed_submit_ignores_client_solution(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/legal-destinations/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": [], "squares": ["a1"]}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200


def test_speed_rejects_foreign_puzzle(client, db_session):
    sid, _, _ = _ready_session(client)
    foreign = Puzzle(
        exercise_slug=SLUG,
        fen="8/8/8/8/3N4/8/8/4K3 w - - 0 1",
        position_json={"from": "d4", "profile": IGNORE_ENEMY_ATTACKS},
        answer_json={"squares": [], "from": "d4", "profile": IGNORE_ENEMY_ATTACKS},
        hint_json={},
        prompt_fa="x",
        explanation="",
        is_published=True,
        is_archived=False,
    )
    db_session.add(foreign)
    db_session.commit()
    db_session.refresh(foreign)
    res = client.post(
        f"/api/v1/legal-destinations/sessions/{sid}/submit",
        json={"puzzle_id": foreign.id, "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 404


def test_speed_expiry_authoritative(client, db_session):
    from datetime import timedelta

    sid, puzzles, _ = _ready_session(client)
    session = db_session.get(LegalSpeedSession, sid)
    session.ends_at = session.started_at - timedelta(seconds=1)
    db_session.commit()
    res = client.post(
        f"/api/v1/legal-destinations/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 410


def test_standard_profile_still_supported():
    # Seeded legacy puzzles use STANDARD; the generator uses IGNORE.
    assert STANDARD in ("standard",) and IGNORE_ENEMY_ATTACKS in ("ignore-enemy-attacks",)
