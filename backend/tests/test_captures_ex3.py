"""Exercise 3 (Captures) production coverage: generator + speed + scoring.

Targeted spec tests beyond the legacy seed tests in test_captures.py:
- per-piece capture rules (sliders blocked, knight jumps, pawn diagonals)
  under the generator's IGNORE_ENEMY_ATTACKS profile
- defense irrelevance: a defended black piece stays a correct capture
- set semantics, malformed payloads, exact scoring incl. zero-target +5
- dynamic generator validity (one white hunter, 3-8 black, variety,
  blockers, bounded retries, no answer leak from endpoints)
- practice next + speed session lifecycle (20-buffer, 60s, report,
  authoritative expiry, client-solution ignored)
"""

import random

import chess
import pytest

from app.modules.captures import generator as gen
from app.modules.captures import sessions as session_service
from app.modules.captures.models import CaptureSpeedSession
from app.modules.captures.scoring import score_squares
from app.modules.captures.validator import (
    IGNORE_ENEMY_ATTACKS,
    SLUG,
    capturable_squares,
    validate,
)
from app.modules.exercises import registry
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def caps(fen: str, hunter: str, profile: str = IGNORE_ENEMY_ATTACKS) -> set[str]:
    return set(capturable_squares(fen, hunter, profile))


# --- Rook ---


def test_rook_reachable_capture():
    assert caps("8/8/8/3p4/3R4/8/8/8 w - - 0 1", "d4") == {"d5"}


def test_rook_blocked_capture():
    # Friendly... no: black pawn d5 blocks, black pawn d6 hides behind it.
    got = caps("8/8/3p4/3p4/3R4/8/8/8 w - - 0 1", "d4")
    assert got == {"d5"}


def test_rook_multiple_captures_rank_and_file():
    got = caps("8/8/8/8/p2R3p/8/8/8 w - - 0 1", "d4")
    assert got == {"a4", "h4"}


# --- Bishop ---


def test_bishop_diagonal_capture():
    assert caps("8/8/8/8/2B5/8/8/8 w - - 0 1", "c4") == set()  # no enemies: nothing
    assert caps("8/8/8/3p4/2B5/8/8/8 w - - 0 1", "c4") == {"d5"}


def test_bishop_blocked_diagonal():
    # Black pawn d5 shields black bishop e6 behind it.
    got = caps("8/8/4b3/3p4/2B5/8/8/8 w - - 0 1", "c4")
    assert got == {"d5"}


# --- Queen ---


def test_queen_rank_and_diagonal_captures():
    got = caps("8/8/8/3pp3/3Q4/8/8/8 w - - 0 1", "d4")
    assert got == {"d5", "e5"}


def test_queen_blocker_shields_behind():
    # Black pawn d5 shields black rook d7; g4 still capturable on the rank.
    got = caps("8/3r4/8/3p4/3Q3p/8/8/8 w - - 0 1", "d4")
    assert got == {"d5", "h4"}


# --- Knight ---


def test_knight_valid_capture():
    assert caps("8/8/4p3/8/3N4/8/8/8 w - - 0 1", "d4") == {"e6"}


def test_knight_nearby_invalid_square():
    # e5 is adjacent but not a knight destination: not capturable.
    assert caps("8/8/8/4p3/3N4/8/8/8 w - - 0 1", "d4") == set()


def test_knight_blocker_does_not_matter():
    # Ring of black pieces around the knight: jumps are unaffected, and the
    # adjacent ones are NOT captures (knight cannot take next to itself).
    got = caps("8/8/8/3ppp2/3pNp2/3ppp2/8/8 w - - 0 1", "e4")
    assert got == set()
    got = caps("8/8/3p1p2/8/3pNp2/8/3p1p2/8 w - - 0 1", "e4")
    assert got == {"d6", "f6", "d2", "f2"}


# --- Pawn ---


def test_pawn_diagonal_captures():
    assert caps("8/8/8/3p1p2/4P3/8/8/8 w - - 0 1", "e4") == {"d5", "f5"}


def test_pawn_forward_piece_is_not_a_capture():
    assert caps("8/8/8/4p3/4P3/8/8/8 w - - 0 1", "e4") == set()


def test_pawn_backward_capture_invalid():
    assert caps("8/8/8/8/4P3/3p4/8/8 w - - 0 1", "e4") == set()


# --- Defense irrelevance (explicit regression protection) ---


def test_defended_piece_stays_capturable_for_sliders():
    # d5 is defended by both c6 and e6 pawns: still a correct capture.
    got = caps("8/8/2p1p3/3p4/3R4/8/8/8 w - - 0 1", "d4")
    assert got == {"d5"}


def test_defense_irrelevant_in_validation():
    # Even a queen defended by three pieces is a correct answer.
    answer = {"squares": ["d5"], "from": "d4"}
    out = validate(answer, {"selected_squares": ["d5"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["d5"], "missed": [], "wrong": []}


# --- Set semantics + validation ---


def test_answer_order_irrelevant_and_duplicates_normalized():
    answer = {"squares": ["c4", "f7"]}
    out = validate(answer, {"selected_squares": ["f7", "c4"]})
    assert out.result == AttemptResult.CORRECT
    dup = validate(answer, {"selected_squares": ["c4", "c4", "f7", "f7"]})
    assert dup.result == AttemptResult.CORRECT
    assert dup.detail == {"correct": ["c4", "f7"], "missed": [], "wrong": []}


def test_malformed_and_impossible_squares_are_wrong():
    answer = {"squares": ["d5"]}
    out = validate(answer, {"selected_squares": ["d5", "zzz"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["wrong"] == ["zzz"]
    assert validate(answer, {"selected_squares": ["h8"]}).result == AttemptResult.WRONG


def test_selecting_hunter_or_empty_square_is_wrong():
    # d4 holds the white hunter itself; e3 is empty: neither is a capture.
    answer = {"squares": ["d5"], "from": "d4"}
    out = validate(answer, {"selected_squares": ["d4", "e3"]})
    assert out.result == AttemptResult.WRONG
    assert sorted(out.detail["wrong"]) == ["d4", "e3"]


def test_selecting_non_capturable_black_piece_is_wrong():
    # d6 hides behind d5: selecting it is wrong even though occupied by black.
    answer = {"squares": ["d5"], "from": "d4"}
    out = validate(answer, {"selected_squares": ["d5", "d6"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail == {"correct": ["d5"], "missed": [], "wrong": ["d6"]}


def test_client_solution_fields_ignored():
    answer = {"squares": ["d5"], "from": "d4"}
    out = validate(answer, {"selected_squares": ["a1"], "squares": ["a1"], "from": "a1"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["d5"]


# --- Scoring (exact spec formula) ---


def test_scoring_spec_examples():
    # Select all three -> 3*5 = 15.
    v = validate({"squares": ["c4", "f7", "h5"]}, {"selected_squares": ["c4", "f7", "h5"]})
    assert v.result == AttemptResult.CORRECT
    assert score_squares(v) == 15.0
    # Select [c4, f7] -> 2*5 - 1 = 9.
    v = validate({"squares": ["c4", "f7", "h5"]}, {"selected_squares": ["c4", "f7"]})
    assert v.result == AttemptResult.PARTIAL
    assert score_squares(v) == 9.0
    # Select [c4, f7, a1] -> 2*5 - 1 - 2 = 7.
    v = validate({"squares": ["c4", "f7", "h5"]}, {"selected_squares": ["c4", "f7", "a1"]})
    assert score_squares(v) == 7.0
    # Select nothing -> 0 - 3 = -3 (negative kept, not clamped).
    v = validate({"squares": ["c4", "f7", "h5"]}, {"selected_squares": []})
    assert score_squares(v) == -3.0


def test_zero_target_scoring():
    v = validate({"squares": []}, {"selected_squares": []})
    assert v.result == AttemptResult.CORRECT
    assert score_squares(v) == 5.0
    v = validate({"squares": []}, {"selected_squares": ["a1"]})
    assert v.result == AttemptResult.WRONG
    assert score_squares(v) == -2.0
    v = validate({"squares": []}, {"selected_squares": ["a1", "b2"]})
    assert score_squares(v) == -4.0


def test_scorer_registered_for_slug():
    assert registry.get_scorer(SLUG) is not None
    assert registry.score_for_answer(SLUG, validate({"squares": []}, {"selected_squares": []})) == 5.0


# --- Generator ---


def _assert_hunter_vs_black(fen: str, hunter_sq: str, piece_type: str):
    board = chess.Board(fen)  # raises on malformed FEN
    whites = [sq for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.color == chess.WHITE]
    blacks = [sq for sq in chess.SQUARES if (p := board.piece_at(sq)) and p.color == chess.BLACK]
    assert len(whites) == 1, f"exactly one white hunter in {fen}"
    hunter = board.piece_at(whites[0])
    assert hunter is not None and hunter.symbol().lower() == piece_type
    assert chess.square_name(whites[0]) == hunter_sq
    assert 3 <= len(blacks) <= 8, f"3-8 black pieces in {fen}"
    assert board.turn == chess.WHITE


def test_generator_valid_positions_and_variety():
    rng = random.Random(2026)
    seen_types: set[str] = set()
    seen_zero = False
    seen_multi = False
    for _ in range(40):
        data = gen.generate_question_data(rng)
        assert data["fen"] and data["from"] and data["prompt_fa"]
        assert data["profile"] == IGNORE_ENEMY_ATTACKS
        _assert_hunter_vs_black(data["fen"], data["from"], data["piece_type"])
        seen_types.add(data["piece_type"])
        # Stored answer recomputes independently (pseudo-legal captures).
        board = chess.Board(data["fen"])
        origin = chess.parse_square(data["from"])
        # Set: promotion captures generate 4 moves (q/r/b/n) to one square.
        expected = sorted(
            {
                chess.square_name(m.to_square)
                for m in board.pseudo_legal_moves
                if m.from_square == origin and board.is_capture(m)
            }
        )
        assert data["squares"] == expected
        if not expected:
            seen_zero = True
        if len(expected) >= 2:
            seen_multi = True
        assert data["prompt_fa"].startswith("کدام مهره‌های سیاه")
    assert seen_types == {"p", "n", "b", "r", "q"}
    assert seen_zero  # zero-capture puzzles occur occasionally
    assert seen_multi  # multiple simultaneous captures occur


def test_generator_blockers_create_contrast():
    # Across slider puzzles, some black piece must be non-capturable
    # (shielded behind a capture or off-ray decoy): education, not noise.
    rng = random.Random(99)
    contrast = False
    for _ in range(40):
        data = gen.generate_question_data(rng, piece_type="r")
        board = chess.Board(data["fen"])
        occupied_black = {
            chess.square_name(sq)
            for sq in chess.SQUARES
            if (p := board.piece_at(sq)) and p.color == chess.BLACK
        }
        if occupied_black - set(data["squares"]):
            contrast = True
            break
    assert contrast


def test_generator_all_piece_types_placeable():
    rng = random.Random(7)
    for ptype in ("p", "n", "b", "r", "q"):
        pos = gen.generate_position_data(rng, piece_type=ptype)
        board = chess.Board(pos["fen"])
        assert board.piece_at(chess.parse_square(pos["from"])).symbol().lower() == ptype


def test_generator_zero_target_mode():
    rng = random.Random(11)
    for _ in range(5):
        pos = gen.generate_position_data(rng, zero_target=True)
        assert pos["squares"] == []
        _assert_hunter_vs_black(pos["fen"], pos["from"], pos["piece_type"])


def test_generator_bounded_failure():
    rng = random.Random(0)
    with pytest.raises(ValueError):
        gen.generate_position_data(rng, piece_type="x")


def test_generator_persists_and_dedups(db_session):
    rng = random.Random(42)
    p1 = gen.create_puzzle(db_session, rng)
    assert p1.answer_json["squares"] == gen.question_for_position(
        p1.fen, p1.position_json["from"], p1.position_json["profile"]
    )["squares"]
    assert p1.position_json["profile"] == IGNORE_ENEMY_ATTACKS
    p2 = gen.create_puzzle(db_session, rng, exclude_ids={p1.id})
    assert p2.id != p1.id
    for _ in range(6):
        gen.create_puzzle(db_session, rng)
    ratings = {p.initial_rating for p in db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()}
    assert len(ratings) >= 3


# --- Practice + speed API ---


def test_practice_next_hides_answer(client, db_session):
    res = client.post("/api/v1/captures/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] and body["prompt_fa"]
    assert "answer_json" not in body
    assert body["position_json"]["from"]
    assert body["exercise_slug"] == SLUG


def _open(client):
    body = client.post("/api/v1/captures/sessions", json={}).json()
    assert body["status"] == "preparing"
    return body["session_id"]


def _prepare(client, session_id, count=20):
    res = client.post(f"/api/v1/captures/sessions/{session_id}/puzzles", json={"count": count})
    assert res.status_code == 200, res.text
    return res.json()


def _start(client, session_id):
    res = client.post(f"/api/v1/captures/sessions/{session_id}/start")
    assert res.status_code == 200, res.text
    return res.json()


def _ready_session(client, count=20):
    sid = _open(client)
    puzzles = _prepare(client, sid, count)
    started = _start(client, sid)
    return sid, puzzles, started


def test_speed_lifecycle_buffer_and_clock(client, db_session):
    sid = _open(client)
    res = client.post(f"/api/v1/captures/sessions/{sid}/start")
    assert res.status_code == 409
    _prepare(client, sid, 19)
    assert client.post(f"/api/v1/captures/sessions/{sid}/start").status_code == 409
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
        f"/api/v1/captures/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["attempt"]["mode"] == "practice"
    assert payload["attempt"]["rating_delta"] is None
    assert payload["session"]["attempted"] == 1
    report = client.get(f"/api/v1/captures/sessions/{sid}/report").json()
    assert report["session"]["attempted"] == 1
    assert len(report["entries"]) == 1
    assert {"correct", "missed", "wrong"} <= set(report["entries"][0].keys())
    attempts = db_session.query(Attempt).order_by(Attempt.id).all()
    assert sum(a.score for a in attempts) == report["session"]["score"]


def test_speed_submit_ignores_client_solution(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/captures/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": [], "squares": ["a1"]}},
    )
    assert res.status_code == 200


def test_speed_rejects_foreign_puzzle(client, db_session):
    sid, _, _ = _ready_session(client)
    foreign = Puzzle(
        exercise_slug=SLUG,
        fen="8/8/8/8/3N4/8/8/8 w - - 0 1",
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
        f"/api/v1/captures/sessions/{sid}/submit",
        json={"puzzle_id": foreign.id, "answer": {"selected_squares": []}},
    )
    assert res.status_code == 404


def test_speed_expiry_authoritative(client, db_session):
    from datetime import timedelta

    sid, puzzles, _ = _ready_session(client)
    session = db_session.get(CaptureSpeedSession, sid)
    session.ends_at = session.started_at - timedelta(seconds=1)
    db_session.commit()
    res = client.post(
        f"/api/v1/captures/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
    )
    assert res.status_code == 410


def test_speed_rejects_submit_before_start(client, db_session):
    sid = _open(client)
    batch = _prepare(client, sid, 20)
    res = client.post(
        f"/api/v1/captures/sessions/{sid}/submit",
        json={"puzzle_id": batch[0]["id"], "answer": {"selected_squares": []}},
    )
    assert res.status_code == 409
