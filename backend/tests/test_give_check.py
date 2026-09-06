"""Exercise 5 (Giving Check): checking-move sets + arrows + scoring + sessions.

Covers the exercise spec:
- basic checks by every piece type (pawn/knight/bishop/rook/queen)
- single / multiple / zero checking moves
- captures with check, ordinary moves with check
- discovered checks (answer = moving piece from->to)
- double check (one move = one answer)
- legality: pins, self-check exposure, illegal moves
- king NEVER a checking piece (excluded + never accepted)
- pawn checks, pawn captures with check, promotions (distinct choices)
- en passant (checking and non-checking)
- starting positions already in check are rejected by the generator
- set semantics: order independence, duplicates, direction matters
- scoring formula incl. zero-target, and security (client cannot override)
- practice next + speed lifecycle (20-buffer, 60s, report, expiry)
"""

import random

import chess
import pytest

from app.modules.exercises import registry
from app.modules.give_check import generator as gen
from app.modules.give_check import sessions as session_service
from app.modules.give_check.models import GivingCheckSpeedSession
from app.modules.give_check.scoring import score_moves
from app.modules.give_check.validator import (
    SLUG,
    checking_moves,
    either_king_in_check,
    normalize_move_uci,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def moveset(fen: str) -> set[str]:
    return set(checking_moves(fen))


def answer(*ucis: str) -> dict:
    return {"moves": list(ucis)}


def attempt(*items) -> dict:
    return {"moves": list(items)}


# --- Basic checks by piece type ---


def test_rook_direct_check():
    assert moveset("4k3/8/8/8/8/8/8/R3K3 w - - 0 1") == {"a1a8"}


def test_bishop_direct_check():
    assert "c4b5" in moveset("4k3/8/8/8/2B5/8/8/4K3 w - - 0 1")


def test_queen_direct_check():
    found = moveset("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert "d1h5" in found


def test_knight_direct_check():
    assert "b5d6" in moveset("4k3/8/8/1N6/8/8/8/4K3 w - - 0 1")


def test_pawn_push_check():
    assert moveset("8/8/5k2/8/4P3/8/8/4K3 w - - 0 1") == {"e4e5"}


def test_rook_file_checks():
    # Every rook move up the open a-file checks the cornered king.
    assert moveset("k7/8/8/8/8/8/8/R3K3 w - - 0 1") == {
        "a1a2",
        "a1a3",
        "a1a4",
        "a1a5",
        "a1a6",
        "a1a7",
    }


def test_multiple_checking_moves():
    found = moveset("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
    assert len(found) > 1
    assert {"d4d8", "d4h8", "d4a4"} <= found


def test_no_checking_moves():
    assert moveset("4k3/8/8/8/8/5N2/5P2/4K3 w - - 0 1") == set()


# --- Captures ---


def test_capture_with_check():
    assert "d4d5" in moveset("8/8/4k3/3p4/3Q4/8/8/4K3 w - - 0 1")


def test_pawn_capture_with_check():
    # White pawn e5 takes f6, checking the black king on e7... verify
    # directly: the capture must appear exactly when it checks.
    fen = "4k3/8/8/4Pp2/8/8/8/4K3 w - f6 0 1"
    board = chess.Board(fen)
    assert chess.Move.from_uci("e5f6") in board.legal_moves
    board.push(chess.Move.from_uci("e5f6"))
    try:
        expected = board.is_check()
    finally:
        board.pop()
    assert ("e5f6" in moveset(fen)) == expected


# --- Discovered and double checks ---


def test_discovered_check_answer_is_the_moving_piece():
    # The knight blocks the b2-h8 diagonal; every knight move off that
    # diagonal uncovers the bishop's check. The answer is the knight's
    # own from->to, never "b2->h8".
    found = moveset("7k/8/8/8/3N4/8/1B6/4K3 w - - 0 1")
    assert "d4f5" in found
    assert "b2h8" not in found
    assert all(uci[:4] != "b2h8" for uci in found)


def test_double_check_is_a_single_answer():
    # d4f5 uncovers Bb2 AND attacks g7 with the knight: double check,
    # still exactly one arrow.
    fen = "8/6k1/8/8/3N4/8/1B6/4K3 w - - 0 1"
    found = moveset(fen)
    assert "d4f5" in found
    assert checking_moves(fen).count("d4f5") == 1
    board = chess.Board(fen)
    board.push(chess.Move.from_uci("d4f5"))
    try:
        assert board.is_check()
        attackers = list(board.attackers(chess.WHITE, board.king(chess.BLACK)))
        assert len(attackers) == 2
    finally:
        board.pop()


# --- Legality ---


def test_blocked_path_is_not_an_answer():
    # d1d8 looks like check but the d7 pawn blocks it.
    assert "d1d8" not in moveset("4k3/3p4/8/8/8/8/8/3QK3 w - - 0 1")


def test_pinned_piece_cannot_leave_its_line():
    # Qe2 is pinned to the e-file; leaving it exposes the white king.
    found = moveset("3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
    assert "e2h5" not in found
    assert "e2e7" in found


def test_move_must_not_expose_own_king():
    # A random checking-looking move that leaves the mover in check is
    # simply absent from the legal checking set.
    for uci in moveset("3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1"):
        board = chess.Board("3kr3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
        assert chess.Move.from_uci(uci) in board.legal_moves


def test_illegal_move_is_wrong():
    out = validate(answer("d4d8"), attempt({"from": "d1", "to": "d8"}))
    assert out.result == AttemptResult.WRONG


def test_legal_non_check_is_wrong():
    out = validate(
        answer(*sorted(moveset("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"))),
        attempt({"from": "d4", "to": "d5"}),
    )
    assert out.result == AttemptResult.WRONG


# --- King exclusion ---


def test_king_moves_are_never_answers():
    fens = [
        "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1",
        "7k/8/8/8/3N4/8/1B6/4K3 w - - 0 1",
        "k7/8/8/8/8/8/5K2/R7 w - - 0 1",
        "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
    ]
    for fen in fens:
        board = chess.Board(fen)
        king_squares = {
            chess.square_name(sq)
            for sq in chess.SQUARES
            if board.piece_at(sq) is not None
            and board.piece_at(sq).piece_type == chess.KING
        }
        for uci in moveset(fen):
            assert uci[:2] not in king_squares, (fen, uci)


def test_king_origin_arrow_is_not_accepted():
    # Even a legal king move that uncovers a rook check is rejected:
    # the king is never a checking piece in this exercise.
    fen = "k7/8/8/8/8/8/5K2/R7 w - - 0 1"
    board = chess.Board(fen)
    assert chess.Move.from_uci("f2e3") in board.legal_moves
    out = validate(answer(*sorted(moveset(fen))), attempt({"from": "f2", "to": "e3"}))
    assert out.result in (AttemptResult.WRONG, AttemptResult.PARTIAL)
    assert "f2e3" not in out.detail["correct"]


def test_castling_is_never_an_answer():
    found = moveset("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    assert "e1g1" not in found
    assert "e1c1" not in found


# --- Promotions ---


def test_promotion_check_is_distinct_per_choice():
    found = moveset("7k/6P1/8/8/8/8/8/4K3 w - - 0 1")
    assert "g7g8q" in found
    assert "g7g8r" in found
    assert "g7g8n" not in found
    assert "g7g8b" not in found


def test_promotion_requires_the_piece_letter():
    out = validate(answer("g7g8q"), attempt({"from": "g7", "to": "g8"}))
    assert out.result == AttemptResult.WRONG
    out = validate(answer("g7g8q"), attempt({"from": "g7", "to": "g8", "promotion": "q"}))
    assert out.result == AttemptResult.CORRECT
    out = validate(answer("g7g8q", "g7g8r"), attempt({"from": "g7", "to": "g8", "promotion": "r"}))
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["g7g8r"]
    assert out.detail["missed"] == ["g7g8q"]


def test_bad_promotion_letter_is_wrong():
    out = validate(answer("g7g8q"), attempt({"from": "g7", "to": "g8", "promotion": "k"}))
    assert out.result == AttemptResult.WRONG


# --- En passant ---


def test_en_passant_check_counts():
    fen = "8/4k3/8/3pP3/8/8/8/4K3 w - d6 0 1"
    board = chess.Board(fen)
    assert chess.Move.from_uci("e5d6") in board.legal_moves
    board.push(chess.Move.from_uci("e5d6"))
    try:
        assert board.is_check()
    finally:
        board.pop()
    assert "e5d6" in moveset(fen)


def test_en_passant_without_check_is_no_answer():
    assert moveset("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1") == set()


# --- Starting position must not be in check ---


def test_white_already_in_check_detected():
    assert either_king_in_check("3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1") is True


def test_black_already_in_check_detected():
    assert either_king_in_check("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1") is True


def test_clean_position_not_flagged():
    assert either_king_in_check("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1") is False


def test_generator_rejects_in_check_positions():
    with pytest.raises(ValueError):
        gen.question_for_fen("3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1")
    with pytest.raises(ValueError):
        gen.question_for_fen("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1")
    with pytest.raises(ValueError):
        gen.question_for_fen("not a fen")


def test_generator_accepts_valid_position():
    data = gen.question_for_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    assert data["moves"] == ["a1a8"]
    assert data["prompt_fa"]


# --- Set semantics ---


def test_order_independence():
    expected = answer("d4d8", "d4h8")
    out = validate(expected, attempt({"from": "d4", "to": "h8"}, {"from": "d4", "to": "d8"}))
    assert out.result == AttemptResult.CORRECT


def test_duplicate_arrows_normalized():
    expected = answer("d4d8", "d4h8")
    out = validate(
        expected,
        attempt(
            {"from": "d4", "to": "d8"},
            {"from": "d4", "to": "d8"},
            {"from": "d4", "to": "h8"},
        ),
    )
    assert out.result == AttemptResult.CORRECT
    assert out.detail["wrong"] == []


def test_direction_matters():
    expected = answer("a1a8")
    out = validate(expected, attempt({"from": "a8", "to": "a1"}))
    assert out.result == AttemptResult.WRONG


def test_partial_result():
    out = validate(answer("d4d8", "d4h8"), attempt({"from": "d4", "to": "d8"}))
    assert out.result == AttemptResult.PARTIAL
    assert out.detail == {"correct": ["d4d8"], "missed": ["d4h8"], "wrong": []}


def test_mixed_correct_missed_wrong():
    out = validate(
        answer("d4d8", "d4h8"),
        attempt({"from": "d4", "to": "d8"}, {"from": "e2", "to": "e4"}),
    )
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["d4d8"]
    assert out.detail["missed"] == ["d4h8"]
    assert out.detail["wrong"] == ["e2e4"]


def test_plain_uci_strings_accepted():
    out = validate(answer("d4d8"), attempt("d4d8"))
    assert out.result == AttemptResult.CORRECT


def test_malformed_arrows_are_wrong_not_crashes():
    out = validate(answer("d4d8"), attempt({"from": "d9", "to": "d8"}, None, 42, {"from": "d4"}))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["wrong"]) == 4
    out = validate(answer("d4d8"), {})
    assert out.result == AttemptResult.WRONG
    out = validate({}, attempt({"from": "d4", "to": "d8"}))
    assert out.result == AttemptResult.WRONG
    out = validate(None, attempt({"from": "d4", "to": "d8"}))  # type: ignore[arg-type]
    assert out.result == AttemptResult.WRONG


def test_zero_target_empty_is_correct():
    out = validate(answer(), attempt())
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": [], "missed": [], "wrong": []}


def test_zero_target_with_arrow_is_wrong():
    out = validate(answer(), attempt({"from": "e2", "to": "e4"}))
    assert out.result == AttemptResult.WRONG


# --- Scoring ---


def _validation_for(expected: list[str], selected: list[dict]) -> object:
    return validate({"moves": expected}, {"moves": selected})


def test_score_all_correct():
    assert score_moves(_validation_for(["a1a8"], [{"from": "a1", "to": "a8"}])) == 5.0


def test_score_partial_and_mixed():
    # 1 correct (+5), 1 missed (-1), 1 wrong (-2) = 2.
    v = _validation_for(["d4d8", "d4h8"], [{"from": "d4", "to": "d8"}, {"from": "e2", "to": "e4"}])
    assert score_moves(v) == 2.0


def test_score_negative_allowed():
    v = _validation_for(["d4d8"], [{"from": "e2", "to": "e4"}, {"from": "a2", "to": "a4"}])
    assert v.result == AttemptResult.WRONG
    assert score_moves(v) == -5.0


def test_score_zero_target_bonus():
    v = _validation_for([], [])
    assert score_moves(v) == 5.0
    v = _validation_for([], [{"from": "e2", "to": "e4"}])
    assert score_moves(v) == -2.0


def test_scorer_registered():
    from app.modules.exercises import registry as reg

    assert reg.get_validator(SLUG) is not None
    assert reg.get_scorer(SLUG) is not None


# --- Security: client cannot override authoritative data ---


def test_client_extra_fields_ignored():
    out = validate(
        answer("d4d8"),
        {
            "moves": [{"from": "d4", "to": "d5"}],
            "fen": "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1",
            "result": "correct",
            "score": 100.0,
        },
    )
    assert out.result == AttemptResult.WRONG


def test_normalize_move_uci_shapes():
    assert normalize_move_uci({"from": " E2 ", "to": "e4"}) == "e2e4"
    assert normalize_move_uci("D4D8") == "d4d8"
    assert normalize_move_uci({"from": "g7", "to": "g8", "promotion": "Q"}) == "g7g8q"
    assert normalize_move_uci({"from": "g7", "to": "g8", "promotion": "k"}) is None
    assert normalize_move_uci({"from": "e2", "to": "e9"}) is None
    assert normalize_move_uci(42) is None


# --- Generator sampling ---


def test_generate_question_data_bounded():
    rng = random.Random(7)
    data = gen.generate_question_data(rng)
    assert data["fen"]
    assert data["moves"] == checking_moves(data["fen"])
    assert not either_king_in_check(data["fen"])


def test_create_puzzle_persists_answer(db_session):
    rng = random.Random(11)
    puzzle = gen.create_puzzle(db_session, rng)
    assert puzzle.exercise_slug == SLUG
    assert puzzle.is_published and not puzzle.is_archived
    assert puzzle.answer_json["moves"] == checking_moves(puzzle.fen)
    assert "moves" not in puzzle.position_json


# --- API flow ---


def _practice_puzzle(client) -> dict:
    res = client.post("/api/v1/giving-check/next", json={"exclude_ids": []})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    return body


def test_api_next_and_submit(client, db_session):
    body = _practice_puzzle(client)
    expected = checking_moves(body["fen"])
    full = [{"from": u[:2], "to": u[2:4], **({"promotion": u[4]} if len(u) == 5 else {})} for u in expected]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"moves": full}, "mode": "practice"},
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["result"] == "correct"
    assert payload["score"] == (float(len(expected) * 5) if expected else 5.0)
    assert payload["rating_delta"] is None

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"moves": [{"from": "e1", "to": "e2"}]}, "mode": "practice"},
    )
    assert bad.json()["result"] in ("wrong", "partial")
    assert bad.json()["rating_delta"] is None


def test_api_practice_submit_ignores_client_fen(client):
    body = _practice_puzzle(client)
    res = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": body["id"],
            "answer": {"moves": [], "fen": "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"},
            "mode": "practice",
        },
    )
    assert res.status_code == 200
    # Graded against the stored puzzle, not the client-supplied FEN.
    assert res.json()["result"] == ("correct" if not checking_moves(body["fen"]) else "wrong")


def test_api_puzzle_detail_hides_answer(client):
    body = _practice_puzzle(client)
    res = client.get(f"/api/v1/puzzles/{body['id']}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_speed_lifecycle(client):
    opened = client.post("/api/v1/giving-check/sessions", json={})
    assert opened.status_code == 200
    sid = opened.json()["session_id"]

    early = client.post(
        f"/api/v1/giving-check/sessions/{sid}/submit",
        json={"puzzle_id": 1, "answer": {"moves": []}},
    )
    assert early.status_code == 409

    prepared = client.post(f"/api/v1/giving-check/sessions/{sid}/puzzles", json={"count": 20})
    assert prepared.status_code == 200
    assert len(prepared.json()) >= 20
    assert all("answer_json" not in p for p in prepared.json())

    started = client.post(f"/api/v1/giving-check/sessions/{sid}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    first_id = prepared.json()[0]["id"]
    first = client.get(f"/api/v1/puzzles/{first_id}").json()
    expected = checking_moves(first["fen"])
    full = [{"from": u[:2], "to": u[2:4], **({"promotion": u[4]} if len(u) == 5 else {})} for u in expected]
    sub = client.post(
        f"/api/v1/giving-check/sessions/{sid}/submit",
        json={"puzzle_id": first_id, "answer": {"moves": full}},
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"

    report = client.get(f"/api/v1/giving-check/sessions/{sid}/report")
    assert report.status_code == 200
    assert len(report.json()["entries"]) == 1

    finished = client.post(f"/api/v1/giving-check/sessions/{sid}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"


def test_speed_requires_full_buffer(client):
    opened = client.post("/api/v1/giving-check/sessions", json={}).json()
    sid = opened["session_id"]
    client.post(f"/api/v1/giving-check/sessions/{sid}/puzzles", json={"count": 5})
    assert client.post(f"/api/v1/giving-check/sessions/{sid}/start").status_code == 409


def test_speed_unknown_session_404(client):
    assert client.get("/api/v1/giving-check/sessions/nope").status_code == 404
