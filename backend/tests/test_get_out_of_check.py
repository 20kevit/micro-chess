"""Get Out of Check: escaping-move sets + arrows + scoring + sessions.

Covers the exercise spec:
- basic state: White in check, not checkmate, >= 1 answer
- capture the checker (accepted) vs capture leaving check (rejected)
- block rook/bishop/queen checks; knight checks never blockable
- king escapes: safe accepted, attacked squares rejected
- double check: only safe king moves (capture-one / block-one invalid)
- multiple answers: complete set, order free, duplicates collapse
- invalid arrows: legal non-resolving, illegal geometry, black pieces,
  malformed input (all safe WRONG)
- scoring: correct*5 - missed*2 - wrong*3, negatives allowed
- generator: validity gates + family/checker mixture + answer variety
- practice next + speed lifecycle (20-buffer, 60s, report)
"""

import random

import chess
import pytest

from app.modules.exercises import registry
from app.modules.get_out_of_check import generator as gen
from app.modules.get_out_of_check import seed as seed_mod
from app.modules.get_out_of_check import sessions as session_service
from app.modules.get_out_of_check.models import GetOutOfCheckSpeedSession
from app.modules.get_out_of_check.scoring import score_moves
from app.modules.get_out_of_check.validator import (
    SLUG,
    escaping_moves,
    is_escaping_move,
    normalize_move_uci,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(fen: str) -> dict:
    return {"fen": fen}


def attempt(*items) -> dict:
    return {"moves": list(items)}


def move(frm: str, to: str, promotion: str | None = None) -> dict:
    body: dict = {"from": frm, "to": to}
    if promotion is not None:
        body["promotion"] = promotion
    return body


def full_answer(fen: str) -> dict:
    """The complete correct submission for a position."""
    return {
        "moves": [
            {"from": u[:2], "to": u[2:4], **({"promotion": u[4]} if len(u) == 5 else {})}
            for u in escaping_moves(fen)
        ]
    }


# --- Basic state ---


def test_white_in_check_not_mate_with_answers():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    board = chess.Board(fen)
    assert board.is_check() is True
    assert board.is_checkmate() is False
    assert len(escaping_moves(fen)) >= 1


def test_not_in_check_has_no_answers():
    fen = "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"
    assert chess.Board(fen).is_check() is False
    assert escaping_moves(fen) == []


def test_checkmate_has_no_answers():
    # Fool's mate: White to move, in check, no legal moves at all.
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1"
    board = chess.Board(fen)
    assert board.is_check() is True
    assert board.is_checkmate() is True
    assert escaping_moves(fen) == []


# --- Category A: capture the checker ---


def test_capture_checker_accepted():
    fen = "4k3/8/8/8/1b6/8/2N5/4K3 w - - 0 1"
    assert "c2b4" in escaping_moves(fen)
    out = validate(answer_for(fen), full_answer(fen))
    assert out.result == AttemptResult.CORRECT


def test_capture_attacker_with_king():
    # Qe2 adjacent, undefended: Kxe2 is the only escape.
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    assert escaping_moves(fen) == ["e1e2"]
    out = validate(answer_for(fen), attempt(move("e1", "e2")))
    assert out.result == AttemptResult.CORRECT


def test_capture_leaving_king_in_check_rejected():
    # c2c3 blocks the queen but the bishop on b4 still checks: illegal.
    fen = "1k2r3/8/8/3Q4/1b6/2P5/8/4K3 w - - 0 1"
    assert "c2c3" not in escaping_moves(fen)
    out = validate(answer_for(fen), attempt(move("c2", "c3")))
    assert out.result == AttemptResult.WRONG


def test_capture_of_defended_checker_rejected():
    # Nf3+ is defended by the g4 pawn: gxf3 is illegal, king must move.
    defended = "4k3/8/8/8/8/5np1/8/4K3 w - - 0 1"
    assert "g2f3" not in escaping_moves(defended)
    out = validate(answer_for(defended), attempt(move("g2", "f3")))
    assert out.result == AttemptResult.WRONG
    assert "g2f3" not in out.detail["correct"]


# --- Category B: block the checking line ---


def test_block_rook_check():
    fen = "4r3/8/8/8/8/3B4/8/4K3 w - - 0 1"
    assert "d3e2" in escaping_moves(fen)
    out = validate(answer_for(fen), attempt(move("d3", "e2")))
    assert out.result == AttemptResult.PARTIAL or out.result == AttemptResult.CORRECT


def test_block_bishop_check():
    # Bb4+ along b4-c3-d2-e1: c2c3 interposes.
    fen = "4k3/8/8/8/1b6/8/2P5/4K3 w - - 0 1"
    assert chess.Board(fen).is_check() is True
    assert "c2c3" in escaping_moves(fen)


def test_block_queen_check():
    # Qb4+ along the 4th rank... use a clean queen line check.
    fen = "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"
    assert "d4d1" in escaping_moves(fen)


def test_pinned_piece_cannot_block():
    # The c1 bishop is pinned by the a1 rook: Bc1-d2 is illegal.
    fen = "4k3/8/8/8/1q6/8/2P5/r1B1K3 w - - 0 1"
    assert "c1d2" not in escaping_moves(fen)
    out = validate(answer_for(fen), attempt(move("c1", "d2")))
    assert out.result == AttemptResult.WRONG


def test_knight_check_never_blockable():
    # Nf3+: no square lies "between" a knight and the king. Every
    # non-king escape must capture the knight; interpositions don't exist.
    fen = "4k3/8/8/8/8/5n2/6P1/4K3 w - - 0 1"
    escapes = escaping_moves(fen)
    assert "g2f3" in escapes  # the capture
    king_sq = "e1"
    non_king = [u for u in escapes if u[:2] != king_sq]
    assert non_king == ["g2f3"]
    # A random interposing-looking move resolves nothing.
    out = validate(answer_for(fen), attempt(move("g2", "g3")))
    assert "g2g3" not in out.detail["correct"]


def test_adjacent_slider_check_not_blockable():
    # Rd1+ from the adjacent square: nothing to interpose.
    fen = "3k4/8/8/8/8/8/8/3rK3 w - - 0 1"
    escapes = escaping_moves(fen)
    assert escapes  # king moves only (d1 is adjacent, e2 capture... verify below)
    assert all(u[:2] == "e1" for u in escapes)


# --- Category C: king escapes ---


def test_safe_king_move_accepted():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    assert "e1d1" in escaping_moves(fen)
    assert is_escaping_move(fen, "e1", "d1") is True


def test_king_move_into_attack_rejected():
    # d1 and f1 are covered by the checking queen.
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    assert "e1d1" not in escaping_moves(fen)
    assert "e1f1" not in escaping_moves(fen)
    assert is_escaping_move(fen, "e1", "d1") is False
    out = validate(answer_for(fen), attempt(move("e1", "d1")))
    assert out.result == AttemptResult.WRONG


def test_king_move_remaining_in_check_rejected():
    # Qd8 ignores the b1 rook's check: the king stays in check.
    fen = "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"
    out = validate(answer_for(fen), attempt(move("d4", "d8")))
    assert out.result == AttemptResult.WRONG


def test_king_cannot_capture_defended_checker():
    # The g4 pawn defends Nf3: gxf3 is illegal; only king moves escape.
    fen = "4k3/8/8/8/8/5np1/8/4K3 w - - 0 1"
    assert "g2f3" not in escaping_moves(fen)
    for uci in escaping_moves(fen):
        mv = chess.Move.from_uci(uci)
        board = chess.Board(fen)
        assert mv in board.legal_moves, uci


# --- Double check ---


DOUBLE_FEN = "4k3/8/8/8/1b6/5n2/8/4K3 w - - 0 1"


def test_double_check_position_is_genuine():
    board = chess.Board(DOUBLE_FEN)
    assert board.is_check() is True
    assert len(board.checkers()) == 2
    assert board.is_checkmate() is False


def test_double_check_only_king_moves():
    escapes = escaping_moves(DOUBLE_FEN)
    assert escapes
    assert all(u[:2] == "e1" for u in escapes)


def test_double_check_capture_one_checker_invalid():
    # Capturing one checker can never suffice while the other still
    # attacks: every escape starts on e1 (king moves only), and the set
    # contains no capture by a non-king piece.
    escapes = escaping_moves(DOUBLE_FEN)
    assert len(escapes) >= 1
    assert all(u[:2] == "e1" for u in escapes)
    out = validate(answer_for(DOUBLE_FEN), full_answer(DOUBLE_FEN))
    assert out.result == AttemptResult.CORRECT


def test_double_check_block_one_line_invalid():
    # There is no block in the answer set: every escape starts on e1.
    assert all(u[:2] == "e1" for u in escaping_moves(DOUBLE_FEN))


def test_double_check_safe_king_move_valid():
    escapes = escaping_moves(DOUBLE_FEN)
    assert "e1d1" in escapes
    out = validate(answer_for(DOUBLE_FEN), attempt(move("e1", "d1")))
    assert out.result in (AttemptResult.CORRECT, AttemptResult.PARTIAL)
    assert "e1d1" in out.detail["correct"]


def test_double_check_unsafe_king_move_invalid():
    # Squares still attacked after the move never appear as answers.
    escapes = escaping_moves(DOUBLE_FEN)
    for dest in ("d2", "e2", "f2", "d1", "f1"):
        uci = f"e1{dest}"
        expected = uci in escapes
        assert is_escaping_move(DOUBLE_FEN, "e1", dest) == expected, uci


# --- Multiple answers, order, duplicates ---


def test_multiple_escapes_all_accepted():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    assert len(escaping_moves(fen)) > 1
    out = validate(answer_for(fen), full_answer(fen))
    assert out.result == AttemptResult.CORRECT
    assert out.detail["missed"] == [] and out.detail["wrong"] == []


def test_order_does_not_matter():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    moves = list(reversed(full_answer(fen)["moves"]))
    out = validate(answer_for(fen), {"moves": moves})
    assert out.result == AttemptResult.CORRECT


def test_duplicate_arrows_collapse():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    submitted = []
    for u in escaping_moves(fen):
        submitted.extend([u, u])  # every arrow drawn twice
    out = validate(answer_for(fen), {"moves": submitted})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["wrong"] == []


def test_partial_when_one_missed():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    all_moves = escaping_moves(fen)
    assert len(all_moves) >= 2
    out = validate(answer_for(fen), attempt(all_moves[0]))
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == [all_moves[0]]
    assert len(out.detail["missed"]) == len(all_moves) - 1


def test_mixed_correct_missed_wrong():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    all_moves = escaping_moves(fen)
    out = validate(
        answer_for(fen),
        {"moves": [{"from": all_moves[0][:2], "to": all_moves[0][2:4]}, {"from": "a2", "to": "a4"}]},
    )
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == [all_moves[0]]
    assert out.detail["wrong"] == ["a2a4"]


def test_direction_matters():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    out = validate(answer_for(fen), attempt(move("d1", "e1")))
    assert "d1e1" not in out.detail["correct"]


def test_promotion_escape_distinct():
    fen = "3k3n/5KP1/8/8/8/8/8/8 w - - 0 1"
    assert chess.Board(fen).is_check() is True
    escapes = escaping_moves(fen)
    assert "g7h8q" in escapes and "g7h8n" in escapes
    out = validate(answer_for(fen), attempt(move("g7", "h8", "q")))
    assert "g7h8q" in out.detail["correct"]
    # Bare promotion-less arrow does not match a promotion answer.
    out = validate({"fen": fen}, attempt(move("g7", "h8")))
    assert "g7h8q" not in out.detail["correct"]


# --- Invalid arrows ---


def test_legal_non_resolving_move_is_wrong():
    fen = "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"
    out = validate(answer_for(fen), attempt(move("d4", "d8")))
    assert out.result == AttemptResult.WRONG
    assert out.detail["wrong"] == ["d4d8"]


def test_move_by_black_piece_is_wrong():
    # e8 holds the black king: White has no move from there.
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    out = validate(answer_for(fen), attempt(move("e8", "e7")))
    assert out.result == AttemptResult.WRONG


def test_malformed_moves_are_safe_wrong():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    out = validate(answer_for(fen), attempt(move("e9", "d1")))
    assert out.result == AttemptResult.WRONG
    out = validate(answer_for(fen), {"moves": [None, 42, {"from": "e1"}, "zzz"]})
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["wrong"]) == 4
    out = validate(answer_for(fen), {})
    assert out.result == AttemptResult.WRONG
    out = validate({}, attempt(move("e1", "d1")))
    assert out.result == AttemptResult.WRONG
    out = validate(None, attempt(move("e1", "d1")))  # type: ignore[arg-type]
    assert out.result == AttemptResult.WRONG
    out = validate(answer_for("not a fen!!"), attempt(move("e1", "d1")))
    assert out.result == AttemptResult.WRONG


def test_not_in_check_everything_is_wrong():
    fen = "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"
    out = validate(answer_for(fen), {"moves": []})
    assert out.result == AttemptResult.WRONG
    out = validate(answer_for(fen), attempt(move("a1", "a8")))
    assert out.result == AttemptResult.WRONG


def test_client_cannot_force_correctness():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    out = validate(
        answer_for(fen),
        {"moves": [move("e1", "f2")], "result": "correct", "score": 100.0, "fen": fen},
    )
    assert out.result == AttemptResult.WRONG


def test_normalize_move_uci_shapes():
    assert normalize_move_uci({"from": " E1 ", "to": "d1"}) == "e1d1"
    assert normalize_move_uci("E1D1") == "e1d1"
    assert normalize_move_uci({"from": "g7", "to": "h8", "promotion": "Q"}) == "g7h8q"
    assert normalize_move_uci({"from": "g7", "to": "h8", "promotion": "k"}) is None
    assert normalize_move_uci({"from": "e1", "to": "e9"}) is None
    assert normalize_move_uci(42) is None


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Scoring: correct*5 - missed*2 - wrong*3 ---


def test_score_all_correct():
    v = validate(answer_for("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"), attempt(move("e1", "e2")))
    assert v.result == AttemptResult.CORRECT
    assert score_moves(v) == 5.0


def test_score_example_from_spec():
    # Spec example: 4 valid answers; user selects 3 correct + 1 wrong.
    # correct=3, missed=1, wrong=1 -> 3*5 - 1*2 - 1*3 = 10.
    fen = "3k4/8/8/8/3Q4/8/8/1r2K3 w - - 0 1"
    all_moves = escaping_moves(fen)
    assert len(all_moves) == 4, all_moves
    picked = all_moves[:3]
    submitted = [{"from": u[:2], "to": u[2:4]} for u in picked] + [move("a2", "a4")]
    v = validate(answer_for(fen), {"moves": submitted})
    assert v.result == AttemptResult.PARTIAL
    assert v.detail["correct"] == sorted(picked)
    assert len(v.detail["missed"]) == 1
    assert v.detail["wrong"] == ["a2a4"]
    assert score_moves(v) == 10.0


def test_score_some_correct_some_missed():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    all_moves = escaping_moves(fen)
    v = validate(answer_for(fen), attempt(all_moves[0]))
    assert score_moves(v) == float(5 - 2 * (len(all_moves) - 1))


def test_score_all_wrong_negative():
    fen = "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"
    v = validate(answer_for(fen), {"moves": [move("a2", "a4"), move("b2", "b4")]})
    assert v.result == AttemptResult.WRONG
    assert score_moves(v) == float(0 - 2 * len(escaping_moves(fen)) - 2 * 3)


def test_score_empty_submission_misses_everything():
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    v = validate(answer_for(fen), {"moves": []})
    assert v.result == AttemptResult.WRONG
    assert score_moves(v) == -2.0


# --- Seed correctness ---


def _to_uci(frm: str, to: str, promotion: str | None) -> str:
    prom = {"q": "q", "r": "r", "b": "b", "n": "n"}.get(promotion) if promotion else ""
    return f"{frm}{to}{prom}"


def test_seed_count_and_examples_valid(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen
        board = chess.Board(puzzle.fen)
        assert board.is_check() is True
        assert board.is_checkmate() is False
        escapes = escaping_moves(puzzle.fen)
        assert len(escapes) >= 1
        example = puzzle.answer_json["example"]
        uci = _to_uci(example["from"], example["to"], example.get("promotion"))
        assert uci in escapes, puzzle.fen
        # Full-set submission validates CORRECT through the registry path.
        out = registry.validate_answer(SLUG, puzzle.answer_json, full_answer(puzzle.fen))
        assert out.result == AttemptResult.CORRECT, puzzle.fen
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
    assert len({p.initial_rating for p in puzzles}) >= 5


def test_seed_title_is_official(db_session):
    from app.modules.exercises.models import Exercise

    seed_mod.seed_db(db_session)
    exercise = db_session.get(Exercise, SLUG)
    assert exercise is not None
    assert exercise.title_fa == "رفع کیش"


# --- Generator ---


def test_question_for_fen_gates():
    with pytest.raises(ValueError):
        gen.question_for_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")  # not in check
    with pytest.raises(ValueError):
        gen.question_for_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1")  # checkmate
    with pytest.raises(ValueError):
        gen.question_for_fen("not a fen")
    data = gen.question_for_fen("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
    assert data["moves"] == escaping_moves(data["fen"])
    assert data["prompt_fa"]


def test_generated_puzzles_satisfy_mandatory_gates():
    rng = random.Random(1234)
    for _ in range(25):
        data = gen.generate_question_data(rng)
        board = chess.Board(data["fen"])  # valid FEN
        assert board.is_valid()
        assert sum(1 for sq in chess.SQUARES if board.piece_at(sq) == chess.Piece(chess.KING, chess.WHITE)) == 1
        assert any(
            p.color == chess.BLACK for sq in chess.SQUARES if (p := board.piece_at(sq)) is not None
        )
        assert board.turn == chess.WHITE
        assert board.is_check() is True
        assert board.is_checkmate() is False
        assert data["moves"] == escaping_moves(data["fen"])
        assert len(data["moves"]) >= 1


def test_generated_mixture_covers_checkers_and_doubles():
    rng = random.Random(99)
    checker_types: set[int] = set()
    doubles = 0
    answer_counts: set[int] = set()
    for _ in range(60):
        data = gen.generate_question_data(rng)
        board = chess.Board(data["fen"])
        checkers = board.checkers()
        if len(checkers) > 1:
            doubles += 1
            king_sq = chess.square_name(board.king(chess.WHITE))
            assert all(u[:2] == king_sq for u in data["moves"])
        else:
            piece = board.piece_at(list(checkers)[0])
            assert piece is not None
            checker_types.add(piece.piece_type)
        answer_counts.add(len(data["moves"]))
    assert {chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN} <= checker_types
    assert doubles >= 1
    assert len(answer_counts) >= 3  # healthy 1 / 2 / 3+ variety


def test_create_puzzle_persists_derivable_answer(db_session):
    rng = random.Random(11)
    puzzle = gen.create_puzzle(db_session, rng)
    assert puzzle.exercise_slug == SLUG
    assert puzzle.is_published and not puzzle.is_archived
    assert puzzle.answer_json == {"fen": puzzle.fen}
    assert "moves" not in puzzle.position_json
    out = validate(puzzle.answer_json, full_answer(puzzle.fen))
    assert out.result == AttemptResult.CORRECT


# --- API flow ---


def _practice_puzzle(client) -> dict:
    res = client.post("/api/v1/get-out-of-check/next", json={"exclude_ids": []})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    return body


def test_api_next_and_submit(client, db_session):
    body = _practice_puzzle(client)
    expected = escaping_moves(body["fen"])
    assert len(expected) >= 1
    full = [{"from": u[:2], "to": u[2:4], **({"promotion": u[4]} if len(u) == 5 else {})} for u in expected]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"moves": full}, "mode": "practice"},
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["result"] == "correct"
    assert payload["score"] == float(len(expected) * 5)
    assert payload["rating_delta"] is None

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"moves": [{"from": "a2", "to": "a4"}]}, "mode": "practice"},
    )
    assert bad.json()["result"] in ("wrong", "partial")
    assert bad.json()["rating_delta"] is None


def test_api_next_never_leaks_answer_count(client):
    seen_prompts = set()
    for _ in range(5):
        body = _practice_puzzle(client)
        assert "answer_json" not in body
        assert "moves" not in (body.get("position_json") or {})
        seen_prompts.add(body["id"])
    assert len(seen_prompts) >= 1


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
    # Graded against the stored puzzle (in check, answers missed) -> wrong.
    assert res.json()["result"] == "wrong"


def test_api_puzzle_detail_hides_answer(client):
    body = _practice_puzzle(client)
    res = client.get(f"/api/v1/puzzles/{body['id']}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_speed_lifecycle(client):
    opened = client.post("/api/v1/get-out-of-check/sessions", json={})
    assert opened.status_code == 200
    sid = opened.json()["session_id"]

    early = client.post(
        f"/api/v1/get-out-of-check/sessions/{sid}/submit",
        json={"puzzle_id": 1, "answer": {"moves": []}},
    )
    assert early.status_code == 409

    prepared = client.post(f"/api/v1/get-out-of-check/sessions/{sid}/puzzles", json={"count": 20})
    assert prepared.status_code == 200
    assert len(prepared.json()) >= 20
    assert all("answer_json" not in p for p in prepared.json())

    started = client.post(f"/api/v1/get-out-of-check/sessions/{sid}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    first_id = prepared.json()[0]["id"]
    first = client.get(f"/api/v1/puzzles/{first_id}").json()
    expected = escaping_moves(first["fen"])
    full = [{"from": u[:2], "to": u[2:4], **({"promotion": u[4]} if len(u) == 5 else {})} for u in expected]
    sub = client.post(
        f"/api/v1/get-out-of-check/sessions/{sid}/submit",
        json={"puzzle_id": first_id, "answer": {"moves": full}},
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"

    report = client.get(f"/api/v1/get-out-of-check/sessions/{sid}/report")
    assert report.status_code == 200
    assert len(report.json()["entries"]) == 1

    finished = client.post(f"/api/v1/get-out-of-check/sessions/{sid}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"


def test_speed_requires_full_buffer(client):
    opened = client.post("/api/v1/get-out-of-check/sessions", json={}).json()
    sid = opened["session_id"]
    client.post(f"/api/v1/get-out-of-check/sessions/{sid}/puzzles", json={"count": 5})
    assert client.post(f"/api/v1/get-out-of-check/sessions/{sid}/start").status_code == 409


def test_speed_unknown_session_404(client):
    assert client.get("/api/v1/get-out-of-check/sessions/nope").status_code == 404


def test_speed_submit_rejects_foreign_puzzle(client, db_session):
    opened = client.post("/api/v1/get-out-of-check/sessions", json={}).json()
    sid = opened["session_id"]
    client.post(f"/api/v1/get-out-of-check/sessions/{sid}/puzzles", json={"count": 20})
    client.post(f"/api/v1/get-out-of-check/sessions/{sid}/start")
    foreign = gen.create_puzzle(db_session, random.Random(5))
    res = client.post(
        f"/api/v1/get-out-of-check/sessions/{sid}/submit",
        json={"puzzle_id": foreign.id, "answer": {"moves": []}},
    )
    assert res.status_code == 404


def test_session_model_registered():
    assert GetOutOfCheckSpeedSession.__tablename__ == "get_out_of_check_speed_sessions"
    _ = session_service.MIN_START_BUFFER
