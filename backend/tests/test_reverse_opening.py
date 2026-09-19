"""Reverse Opening: sequences, positions, seed, step API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.reverse_opening import seed as seed_mod
from app.modules.reverse_opening.description import describe_opening
from app.modules.reverse_opening.validator import (
    SLUG,
    START_FEN,
    matched_plies,
    play_sequence,
    position_key,
    sequence_sans,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers

ITALIAN = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]


def answer_for(moves: list[str], target_fen: str | None = None) -> dict:
    target = target_fen or play_sequence(START_FEN, moves).fen()
    return {"start_fen": START_FEN, "target_fen": target, "solutions": [list(moves)]}


# --- Move validation ---


def test_exact_correct_sequence():
    out = validate(answer_for(ITALIAN), {"moves": list(ITALIAN)})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["correct_sequence"] == ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]
    assert out.detail["matched_plies"] == 6
    assert out.detail["expected_plies"] == 6


def test_san_formatting_irrelevant():
    # Identity is positional: the same UCIs always match, whatever the SAN.
    out = validate(answer_for(ITALIAN), {"moves": [" e2e4 ", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]})
    assert out.result == AttemptResult.CORRECT


def test_illegal_move_rejected():
    out = validate(answer_for(ITALIAN), {"moves": ["e2e5", "e7e5"]})
    assert out.result == AttemptResult.WRONG


def test_malformed_move_rejected():
    for bad in (["e2e9"], ["zzz"], [""], [["e2e4"]], [None], ["e2e4", 123]):
        assert validate(answer_for(ITALIAN), {"moves": bad}).result == AttemptResult.WRONG


def test_incomplete_sequence_rejected():
    out = validate(answer_for(ITALIAN), {"moves": ITALIAN[:4]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["matched_plies"] == 4


def test_extra_move_rejected():
    out = validate(answer_for(ITALIAN), {"moves": ITALIAN + ["a2a3"]})
    assert out.result == AttemptResult.WRONG


def test_wrong_legal_sequence_rejected():
    other = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"]  # Ruy Lopez, not Italian
    out = validate(answer_for(ITALIAN), {"moves": other})
    assert out.result == AttemptResult.WRONG
    assert out.detail["matched_plies"] == 4
    assert out.detail["submitted_sequence"][:4] == ["e4", "e5", "Nf3", "Nc6"]


def test_empty_and_missing_moves_rejected():
    assert validate(answer_for(ITALIAN), {"moves": []}).result == AttemptResult.WRONG
    assert validate(answer_for(ITALIAN), {}).result == AttemptResult.WRONG
    assert validate(answer_for(ITALIAN), {"moves": "e2e4"}).result == AttemptResult.WRONG


def test_alternative_line_reaching_target_accepted():
    # Move-order transposition reaching the identical position counts.
    alt = ["g1f3", "b8c6", "e2e4", "e7e5", "f1c4", "f8c5"]
    assert position_key(play_sequence(START_FEN, alt).fen()) == position_key(
        play_sequence(START_FEN, ITALIAN).fen()
    )
    out = validate(answer_for(ITALIAN), {"moves": alt})
    assert out.result == AttemptResult.CORRECT


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Position validation ---


def test_resulting_position_equals_target():
    board = play_sequence(START_FEN, ITALIAN)
    assert position_key(board.fen()) == position_key(answer_for(ITALIAN)["target_fen"])


def test_different_position_rejected():
    out = validate(answer_for(ITALIAN), {"moves": ITALIAN[:-1] + ["f1b5"]})
    assert out.result == AttemptResult.WRONG


def test_side_to_move_difference_detected():
    ans = answer_for(ITALIAN)
    flipped = chess.Board(ans["target_fen"])
    flipped.turn = not flipped.turn
    ans_flipped = dict(ans, target_fen=flipped.fen())
    assert validate(ans_flipped, {"moves": list(ITALIAN)}).result == AttemptResult.WRONG


def test_castling_right_difference_detected():
    board = play_sequence(START_FEN, ["e2e4", "e7e5", "g1f3", "b8c6"])
    intact = position_key(board.fen())
    board.set_castling_fen("-")
    assert position_key(board.fen()) != intact


def test_en_passant_state_detected():
    start = "rnbqkbnr/pppppppp/8/4P3/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    target = play_sequence(start, ["d7d5"]).fen()  # double push leaves ep=d6
    assert " d6 " in target
    ans = {"start_fen": start, "target_fen": target, "solutions": [["d7d5"]]}
    assert validate(ans, {"moves": ["d7d5"]}).result == AttemptResult.CORRECT
    # Same placement via two single pushes sets no ep square: must NOT match.
    assert validate(ans, {"moves": ["d7d6", "d6d5"]}).result == AttemptResult.WRONG


def test_position_key_ignores_clocks():
    assert position_key("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1") == position_key(
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 5 9"
    )


def test_invalid_fens_fail_safe():
    assert validate({"start_fen": "junk", "target_fen": "junk", "solutions": [["e2e4"]]}, {"moves": ["e2e4"]}).result == AttemptResult.WRONG
    with pytest.raises(ValueError):
        play_sequence("junk", ["e2e4"])
    with pytest.raises(ValueError):
        position_key("junk")


# --- Security ---


def test_client_target_fen_ignored():
    ans = answer_for(ITALIAN)
    out = validate(ans, {"moves": list(ITALIAN), "target_fen": START_FEN})
    assert out.result == AttemptResult.CORRECT


def test_client_start_and_solutions_ignored():
    ans = answer_for(ITALIAN)
    out = validate(
        ans,
        {"moves": ["e2e4"], "start_fen": START_FEN, "solutions": [["e2e4"]], "target_fen": START_FEN},
    )
    assert out.result == AttemptResult.WRONG


def test_client_correct_move_flag_ignored():
    ans = answer_for(ITALIAN)
    out = validate(ans, {"moves": ["e2e4"], "result": "correct", "correct_sequence": ["e4"]})
    assert out.result == AttemptResult.WRONG


# --- Seed (independent verification) ---


def test_seed_count_idempotent_shapes(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen == puzzle.position_json["target_fen"]
        assert puzzle.position_json["start_fen"] == START_FEN
        assert puzzle.position_json["mode"] == "reconstruct"
        assert puzzle.position_json["opening_fa"]
        assert "answer_json" not in puzzle.position_json
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published


def test_seed_sequences_reproduce_targets(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    seen = set()
    white_to_move = black_to_move = 0
    for puzzle in puzzles:
        stored = puzzle.answer_json
        assert stored["start_fen"] == START_FEN
        assert len(stored["solutions"]) == 1
        replayed = play_sequence(stored["start_fen"], stored["solutions"][0])
        assert position_key(replayed.fen()) == position_key(stored["target_fen"])
        assert position_key(stored["target_fen"]) == position_key(puzzle.position_json["target_fen"])
        seen.add(position_key(stored["target_fen"]))
        if replayed.turn == chess.WHITE:
            white_to_move += 1
        else:
            black_to_move += 1
        # Validator agrees with the independent replay.
        assert validate(stored, {"moves": stored["solutions"][0]}).result == AttemptResult.CORRECT
    assert len(seen) == 15  # no duplicate targets
    assert white_to_move >= 1 and black_to_move >= 1
    assert len({p.initial_rating for p in puzzles}) >= 4


def test_seed_move_counts_and_openings(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    counts = {len(p.answer_json["solutions"][0]) for p in puzzles}
    assert min(counts) >= 5 and max(counts) <= 10
    assert len(counts) >= 4  # different move counts
    assert len({p.position_json["opening_fa"] for p in puzzles}) >= 8


# --- Step endpoint (legality oracle, no solution leak) ---


def _step(client, db_session, puzzle, fen, moves, frm, to, promotion=None):
    body = {"puzzle_id": puzzle.id, "fen": fen, "moves": moves, "from": frm, "to": to}
    if promotion:
        body["promotion"] = promotion
    return client.post("/api/v1/reverse-opening/step", json=body)


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_step_accepts_legal_move_with_san(client, db_session):
    puzzle = _seeded(db_session)
    res = _step(client, db_session, puzzle, START_FEN, [], "e2", "e4")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["san"] == "e4"
    assert body["moves"] == ["e2e4"]
    assert body["on_track"] is True


def test_step_rejects_illegal_move_and_tampered_history(client, db_session):
    puzzle = _seeded(db_session)
    bad = _step(client, db_session, puzzle, START_FEN, [], "e2", "e5")
    assert bad.json()["ok"] is False
    # Claimed position diverging from replayed history is rejected.
    fake_fen = chess.Board(START_FEN)
    fake_fen.push_san("d4")
    tampered = _step(client, db_session, puzzle, fake_fen.fen(), ["e2e4"], "e7", "e5")
    assert tampered.json()["ok"] is False


def test_step_reports_divergence_without_revealing_solution(client, db_session):
    puzzle = _seeded(db_session)
    res = _step(client, db_session, puzzle, START_FEN, [], "g1", "h3")
    body = res.json()
    assert body["ok"] is True  # legal, but off the canonical line
    assert body["on_track"] is False
    assert "solutions" not in res.text and "answer_json" not in res.text


def test_step_unknown_puzzle_404(client, db_session):
    res = client.post(
        "/api/v1/reverse-opening/step",
        json={"puzzle_id": 999999, "fen": START_FEN, "moves": [], "from": "e2", "to": "e4"},
    )
    assert res.status_code == 404


# --- API submit flow ---


def test_api_list_hides_solution(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    for entry in body:
        assert entry["fen"] == entry["position_json"]["target_fen"]
        assert "answer_json" not in entry
    dumped = res.text
    for token in ("answer_json", "solutions", "correct_sequence", "move_sequence", "correct_moves"):
        assert token not in dumped


def test_api_correct_incomplete_wrong_submit(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    moves = puzzle.answer_json["solutions"][0]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": moves}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["matched_plies"] == len(moves)

    short = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": moves[:2]}, "mode": "practice"},
        headers=headers,
    )
    assert short.json()["result"] == "wrong"

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": ["g1h3", "g8h6"]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": moves}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_description_content():
    text = describe_opening(play_sequence(START_FEN, ITALIAN).fen(), "بازی ایتالیایی")
    assert "بازی ایتالیایی" in text
    assert "e2e4" not in text and "Nf3" not in text
    with pytest.raises(ValueError):
        describe_opening("junk", "x")
