"""Exercise 4 (Undefended Pieces): detection + pins + scoring + sessions.

Covers the spec's mandatory cases:
- basic detection (white/black/defended/multiple/both-colors/zero/king)
- piece types (pawn/knight/bishop/rook/queen/king as attacker/defender)
- sliding blockers, pawn diagonal-only semantics
- absolute pin regressions (pinned defender, pinned attacker, pin-to-queen)
- scoring formula incl. zero-target, selection semantics, security
- practice next + speed lifecycle (20-buffer, 60s, report, expiry)
"""

import random

import chess
import pytest

from app.modules.exercises import registry
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_generated_pool, publish_staged_puzzles
from app.modules.undefended_pieces import generator as gen
from app.modules.undefended_pieces import seed as seed_mod
from app.modules.undefended_pieces import sessions as session_service
from app.modules.undefended_pieces.models import UndefendedSpeedSession
from app.modules.undefended_pieces.scoring import score_squares
from app.modules.undefended_pieces.validator import SLUG, undefended_squares, validate


def undef(fen: str) -> set[str]:
    return set(undefended_squares(fen))


# --- Basic detection ---


def test_undefended_white_piece():
    assert undef("4k3/8/2b5/8/4R3/8/8/4K3 w - - 0 1") == {"e4"}


def test_undefended_black_piece():
    assert undef("4k3/8/5n2/8/8/2B5/8/4K3 w - - 0 1") == {"f6"}


def test_defended_piece_is_not_undefended():
    assert undef("4k3/8/2b5/8/4R3/8/4Q3/4K3 w - - 0 1") == set()


def test_multiple_undefended_both_colors():
    assert undef("8/8/5n2/1k2P3/r7/8/8/R3K3 w - - 0 1") == {"a1", "f6"}


def test_zero_undefended_pieces():
    assert undef("4k3/8/8/8/8/5N2/5P2/4K3 w - - 0 1") == set()


def test_king_never_an_answer():
    # Black king is attacked and undefended but must be excluded.
    assert undef("8/8/8/4k3/8/8/4Q3/4K3 w - - 0 1") == set()


# --- Piece types ---


def test_pawn_attacks_diagonal_only():
    # e4 <-> d5 mutual diagonal attacks; both undefended.
    assert undef("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1") == {"d5", "e4"}
    # Head-to-head pawns do not attack forward.
    assert undef("4k3/8/8/4p3/4P3/8/8/4K3 w - - 0 1") == set()


def test_knight_jump_attack():
    assert undef("4k3/8/8/5n2/3N4/8/8/4K3 w - - 0 1") == {"d4", "f5"}


def test_slider_attacks():
    assert undef("3rk3/8/8/8/8/8/5K2/3R4 w - - 0 1") == {"d1"}


def test_king_as_attacker_counts_but_king_excluded():
    # Kd3 attacks Pc2; Pc2 attacks Kd3 back; only the pawn is an answer.
    assert undef("4k3/8/8/8/8/3k4/2P5/4K3 w - - 0 1") == {"c2"}


def test_king_as_defender_counts():
    # Pe4 attacked by Bc6 but defended by Ke3; Nf6 attacked by Pe5 alone.
    assert undef("4k3/8/2b2n2/4P3/4P3/4K3/8/8 w - - 0 1") == {"f6"}


def test_queen_attack():
    # Qe2 attacks Ke5 down the file (king excluded -> empty).
    assert undef("8/8/8/4k3/8/8/4Q3/4K3 w - - 0 1") == set()
    # Queen defends: covered by test_defended_piece_is_not_undefended.


# --- Sliding blockers ---


def test_sliding_attack_blocked():
    # Pd5 blocks Rd8; Pd5 itself is defended by Rd8.
    assert undef("3rk3/8/8/3p4/3R4/8/8/4K3 w - - 0 1") == set()


def test_blocked_ray_hides_behind():
    board = chess.Board("3rk3/8/8/3p4/3R4/8/8/4K3 w - - 0 1")
    d8 = chess.parse_square("d8")
    d4 = chess.parse_square("d4")
    assert d8 not in board.attackers(chess.BLACK, d4)
    assert d4 not in board.attackers(chess.WHITE, d8)


# --- Absolute pin (mandatory regressions) ---


def test_pinned_defender_does_not_count():
    # Ng2 geometrically defends Re3 but is absolutely pinned to its King.
    assert undef("4k1r1/8/1b6/8/8/4R3/6N1/6K1 w - - 0 1") == {"e3"}
    board = chess.Board("4k1r1/8/1b6/8/8/4R3/6N1/6K1 w - - 0 1")
    assert board.is_pinned(chess.WHITE, chess.parse_square("g2"))


def test_pinned_attacker_does_not_count():
    # Bd7 apparently attacks Re6 but is absolutely pinned to its King.
    assert undef("4k3/3b4/2B1R3/8/8/8/8/4K3 w - - 0 1") == set()
    board = chess.Board("4k3/3b4/2B1R3/8/8/8/8/4K3 w - - 0 1")
    assert board.is_pinned(chess.BLACK, chess.parse_square("d7"))


def test_piece_pinned_to_queen_still_counts():
    # Bd7 shields its QUEEN, not its King: still a valid attacker.
    assert undef("4q2k/3b4/2B1R3/8/8/8/8/K7 w - - 0 1") == {"e6"}
    board = chess.Board("4q2k/3b4/2B1R3/8/8/8/8/K7 w - - 0 1")
    assert not board.is_pinned(chess.BLACK, chess.parse_square("d7"))


# --- Validation semantics ---


def test_validate_exact_partial_wrong():
    answer = {"squares": ["a1", "f6"]}
    assert validate(answer, {"selected_squares": ["f6", "a1"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["a1", "h7"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["a1"], "missed": ["f6"], "wrong": ["h7"]}
    assert validate(answer, {"selected_squares": ["h7"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG


def test_validate_order_and_duplicates_do_not_matter():
    answer = {"squares": ["a1", "f6"]}
    out = validate(answer, {"selected_squares": ["f6", "a1", "a1", "F6"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["a1", "f6"], "missed": [], "wrong": []}


def test_validate_malformed_answer_safe():
    answer = {"squares": ["a1"]}
    out = validate(answer, {"selected_squares": ["a1", "zzz", 42, None]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["a1"]
    assert len(out.detail["wrong"]) == 3


def test_validate_empty_answer():
    answer = {"squares": []}
    ok = validate(answer, {"selected_squares": []})
    assert ok.result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG


def test_validate_ignores_client_side_fields():
    answer = {"squares": ["a1"]}
    out = validate(answer, {"selected_squares": ["h7"], "squares": ["h7"], "fen": "8/8/8/8/8/8/8/8 w - - 0 1"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["a1"]


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Scoring (exact spec formula) ---


def test_scoring_spec_examples():
    v = validate({"squares": ["a1", "f6", "h7"]}, {"selected_squares": ["a1", "f6", "h7"]})
    assert score_squares(v) == 15.0
    v = validate({"squares": ["a1", "f6", "h7"]}, {"selected_squares": ["a1", "f6"]})
    assert v.result == AttemptResult.PARTIAL
    assert score_squares(v) == 9.0
    v = validate({"squares": ["a1", "f6", "h7"]}, {"selected_squares": ["a1", "f6", "b2"]})
    assert score_squares(v) == 7.0
    v = validate({"squares": ["a1", "f6", "h7"]}, {"selected_squares": []})
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
    assert registry.score_for_answer(SLUG, validate({"squares": []}, {"selected_squares": []})) == 5.0


# --- Generator (shared puzzles.db source) ---


def test_generator_uses_shared_source_and_computes_answers():
    rng = random.Random(2026)
    seen_fens: set[str] = set()
    seen_nonempty = False
    for _ in range(10):
        data = gen.generate_question_data(rng)
        assert data["fen"] and data["prompt_fa"] == "کدام مهره‌ها بی‌دفاع هستند؟"
        assert data["squares"] == undefended_squares(data["fen"])
        seen_fens.add(data["fen"])
        if data["squares"]:
            seen_nonempty = True
    assert seen_nonempty  # the bounded search prefers meaningful positions


def test_generator_persists_and_dedups(db_session):
    rng = random.Random(42)
    p1 = gen.create_puzzle(db_session, rng)
    assert p1.answer_json["squares"] == undefended_squares(p1.fen)
    assert p1.position_json == {"fen": p1.fen, "mode": "standard"}
    assert p1.exercise_slug == SLUG
    p2 = gen.create_puzzle(db_session, rng, exclude_ids={p1.id})
    assert p2.id != p1.id


def test_question_for_fen_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        gen.question_for_fen("not-a-fen")


# --- Seed correctness (independent recomputation) ---


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    out = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        attackers = {s for s in board.attackers(not piece.color, sq) if not board.is_pinned(not piece.color, s)}
        if not attackers:
            continue
        defenders = {s for s in board.attackers(piece.color, sq) if not board.is_pinned(piece.color, s)} - {sq}
        if not defenders:
            out.append(chess.square_name(sq))
    return sorted(out)


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    seen_answers = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": "standard"}
        assert puzzle.answer_json["squares"] == _independent(puzzle.fen)
        seen_answers.add(tuple(puzzle.answer_json["squares"]))
        assert puzzle.prompt_fa == "کدام مهره‌ها بی‌دفاع هستند؟"
        assert puzzle.explanation
        assert not puzzle.is_published and puzzle.status == "validated"
    assert len(seen_answers) >= 6  # varied, not trivially repeated


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
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
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "practice",
        },
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert sorted(ok.json()["detail"]["correct"]) == sorted(puzzle.answer_json["squares"])

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": ["h1"]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] in ("wrong", "partial")


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


# --- Practice + speed API ---


@pytest.fixture
def published_pool(db_session):
    seed_mod.seed_db(db_session)
    publish_generated_pool(db_session, SLUG, gen.create_puzzle)


def test_practice_next_hides_answer(client, db_session, published_pool):
    res = client.post("/api/v1/undefended-pieces/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] and body["prompt_fa"]
    assert "answer_json" not in body
    assert body["exercise_slug"] == SLUG


def _open(client):
    body = client.post("/api/v1/undefended-pieces/sessions", json={}).json()
    assert body["status"] == "preparing"
    return body["session_id"]


def _prepare(client, session_id, count=20):
    res = client.post(f"/api/v1/undefended-pieces/sessions/{session_id}/puzzles", json={"count": count})
    assert res.status_code == 200, res.text
    return res.json()


def _start(client, session_id):
    res = client.post(f"/api/v1/undefended-pieces/sessions/{session_id}/start")
    assert res.status_code == 200, res.text
    return res.json()


def _ready_session(client, count=20):
    sid = _open(client)
    puzzles = _prepare(client, sid, count)
    started = _start(client, sid)
    return sid, puzzles, started


def test_speed_lifecycle_buffer_and_clock(client, db_session, published_pool):
    sid = _open(client)
    res = client.post(f"/api/v1/undefended-pieces/sessions/{sid}/start")
    assert res.status_code == 409
    _prepare(client, sid, 19)
    assert client.post(f"/api/v1/undefended-pieces/sessions/{sid}/start").status_code == 409
    _prepare(client, sid, 1)
    started = _start(client, sid)
    assert started["status"] == "active" and started["duration_s"] == 60
    assert started["buffered"] == 20


def test_speed_prepare_hides_answers(client, db_session, published_pool):
    sid = _open(client)
    batch = _prepare(client, sid, 20)
    assert len(batch) == 20
    assert all("answer_json" not in p for p in batch)
    assert len({p["id"] for p in batch}) == 20


def test_speed_submit_and_report(client, db_session, published_pool):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/undefended-pieces/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["attempt"]["mode"] == "practice"
    assert payload["attempt"]["rating_delta"] is None
    assert payload["session"]["attempted"] == 1
    report = client.get(f"/api/v1/undefended-pieces/sessions/{sid}/report").json()
    assert report["session"]["attempted"] == 1
    assert len(report["entries"]) == 1
    assert {"correct", "missed", "wrong"} <= set(report["entries"][0].keys())
    attempts = db_session.query(Attempt).order_by(Attempt.id).all()
    assert sum(a.score for a in attempts) == report["session"]["score"]


def test_speed_submit_ignores_client_solution(client, db_session, published_pool):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/undefended-pieces/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": [], "squares": ["a1"], "fen": "8/8/8/8/8/8/8/8 w - - 0 1"}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200


def test_speed_rejects_foreign_puzzle(client, db_session, published_pool):
    sid, _, _ = _ready_session(client)
    foreign = Puzzle(
        exercise_slug=SLUG,
        fen="8/8/8/8/3N4/8/8/8 w - - 0 1",
        position_json={"fen": "8/8/8/8/3N4/8/8/8 w - - 0 1", "mode": "standard"},
        answer_json={"squares": []},
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
        f"/api/v1/undefended-pieces/sessions/{sid}/submit",
        json={"puzzle_id": foreign.id, "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 404


def test_speed_expiry_authoritative(client, db_session, published_pool):
    from datetime import timedelta

    sid, puzzles, _ = _ready_session(client)
    session = db_session.get(UndefendedSpeedSession, sid)
    session.ends_at = session.started_at - timedelta(seconds=1)
    db_session.commit()
    res = client.post(
        f"/api/v1/undefended-pieces/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 410


def test_speed_rejects_submit_before_start(client, db_session, published_pool):
    sid = _open(client)
    batch = _prepare(client, sid, 20)
    res = client.post(
        f"/api/v1/undefended-pieces/sessions/{sid}/submit",
        json={"puzzle_id": batch[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 409


def test_speed_double_submit_counts_each_time(client, db_session, published_pool):
    # No puzzle_already_answered guard in this exercise family: each submit
    # is a separate attempt row (matches captures behavior).
    sid, puzzles, _ = _ready_session(client)
    headers = make_auth_headers(db_session)
    for _ in range(2):
        res = client.post(
            f"/api/v1/undefended-pieces/sessions/{sid}/submit",
            json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
            headers=headers,
        )
        assert res.status_code == 200
