"""Opening Traps Blindfold: description, SAN rules, multi-solutions, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.opening_traps import seed as seed_mod
from app.modules.opening_traps.description import THEME_FA, describe_position, describe_trap, side_to_move
from app.modules.opening_traps.validator import SLUG, solution_sans, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_staged_puzzles

FEN_LEGAL = "rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5"
FEN_NOAH = "r1bqkbnr/5ppp/p2p4/1pp5/3QP3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 9"
FEN_FOOLS = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
FEN_EVANS = "r2qk1nr/pppb1ppp/2np4/b7/2BpP3/1QP2N2/P4PPP/RNB2RK1 w kq - 2 9"


def answer_for(fen: str, solutions: list[str], theme: str = "TRAP") -> dict:
    return {"fen": fen, "solutions": solutions, "theme": theme}


# --- Description ---


def test_description_has_trap_opening_side():
    text = describe_trap(FEN_LEGAL, "دفاع فیلیدور", "تله لگال")
    assert text.startswith("تله: تله لگال. شروع بازی: دفاع فیلیدور.")
    assert "نوبت سفید است." in text
    assert side_to_move(FEN_LEGAL) == "white"


def test_description_black_to_move():
    text = describe_trap(FEN_FOOLS, "شروع فرعی", "مات احمق")
    assert "نوبت سیاه است." in text
    assert side_to_move(FEN_FOOLS) == "black"


def test_description_piece_names_and_order():
    text = describe_position(FEN_LEGAL)
    for word in ("شاه", "وزیر", "رخ", "فیل", "اسب", "سرباز", "سفید", "سیاه"):
        assert word in text
    assert text.index("مهره‌های سفید") < text.index("مهره‌های سیاه")
    assert text.index("e1") < text.index("d1")  # king before queen


def test_description_squares_sorted():
    assert describe_position(FEN_LEGAL).index("a7") < describe_position(FEN_LEGAL).index("b7")


def test_description_never_contains_fen_or_san():
    text = describe_trap(FEN_LEGAL, "دفاع فیلیدور", "تله لگال")
    assert "rn1qkbnr" not in text
    assert "Nxe5" not in text and "f3e5" not in text


def test_description_never_hints_the_move():
    for item in seed_mod.PUZZLES:
        text = describe_trap(item["fen"], item["opening_fa"], item["trap_fa"])
        board = chess.Board(item["fen"])
        for uci in item["solutions"]:
            assert board.san(chess.Move.from_uci(uci)) not in text


def test_description_deterministic_and_all_themes_known():
    assert describe_trap(FEN_LEGAL, "x", "y") == describe_trap(FEN_LEGAL, "x", "y")
    for item in seed_mod.PUZZLES:
        assert item["theme"] in THEME_FA
    with pytest.raises(ValueError):
        describe_position("not-a-fen")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- SAN parsing ---


def test_san_with_and_without_suffix_same_move():
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
    ans = answer_for(fen, ["h5f7"], "MATE_THREAT")
    assert validate(ans, {"move": "Qxf7#"}).result == AttemptResult.CORRECT
    assert validate(ans, {"move": "Qxf7"}).result == AttemptResult.CORRECT
    assert validate(ans, {"move": "  Qxf7+  "}).result == AttemptResult.CORRECT


def test_invalid_san_rejected():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    for bad in ("zzz", "", "   ", "Q", "e9", "Nxe9", 123, None, {}):
        assert validate(ans, {"move": bad}).result == AttemptResult.WRONG


def test_illegal_san_rejected():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    assert validate(ans, {"move": "Ke2"}).result == AttemptResult.WRONG  # blocked own pawn
    assert validate(ans, {"move": "Qh7#"}).result == AttemptResult.WRONG  # well-formed, not legal


def test_ambiguous_san_rejected():
    # Two knights (e4, h3) can reach g5: bare "Ng5" must not guess.
    fen = "4k3/8/8/8/4N3/7N/8/4K3 w - - 0 1"
    ans = answer_for(fen, ["e4g5"])
    out = validate(ans, {"move": "Ng5"})
    assert out.result == AttemptResult.WRONG
    # Disambiguated forms still work.
    assert validate(ans, {"move": "Neg5"}).result == AttemptResult.CORRECT
    assert validate(ans, {"move": "Nh3g5"}).result == AttemptResult.WRONG


# --- Correct answers (incl. multiple) ---


def test_first_solution_accepted():
    assert validate(answer_for(FEN_LEGAL, ["f3e5"]), {"move": "Nxe5"}).result == AttemptResult.CORRECT


def test_second_solution_accepted():
    ans = answer_for(FEN_NOAH, ["d4c5", "d4g7"], "MATERIAL_WIN")
    assert validate(ans, {"move": "Qxc5"}).result == AttemptResult.CORRECT
    assert validate(ans, {"move": "Qxg7"}).result == AttemptResult.CORRECT


def test_all_seed_solutions_accepted(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        stored = puzzle.answer_json
        sans = solution_sans(stored["fen"], stored["solutions"])
        assert len(sans) == len(stored["solutions"])
        for san in sans:
            out = validate(stored, {"move": san})
            assert out.result == AttemptResult.CORRECT, (puzzle.id, san)
            assert out.detail["theme"] == stored["theme"]
            assert out.detail["correct"] == [san]


def test_correct_detail_carries_move_and_theme():
    out = validate(answer_for(FEN_LEGAL, ["f3e5"], "TRAP"), {"move": "Nxe5"})
    assert out.detail["correct_move"] == "Nxe5"
    assert out.detail["theme"] == "TRAP"
    assert out.detail["missed"] == [] and out.detail["wrong"] == []


# --- Wrong answers ---


def test_legal_but_tactically_wrong_rejected():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    out = validate(ans, {"move": "Bb5+"})  # legal check, not the tactic
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["Nxe5"]
    assert out.detail["wrong"] == ["Bb5+"]
    assert out.detail["correct_move"] == "Nxe5"


def test_empty_and_missing_move_rejected():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    assert validate(ans, {"move": ""}).result == AttemptResult.WRONG
    assert validate(ans, {}).result == AttemptResult.WRONG
    assert validate(ans, {"move": "   "}).result == AttemptResult.WRONG


# --- Security ---


def test_client_fen_ignored():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    out = validate(ans, {"move": "Nxe5", "fen": FEN_NOAH})
    assert out.result == AttemptResult.CORRECT


def test_client_solutions_ignored():
    ans = answer_for(FEN_LEGAL, ["f3e5"])
    out = validate(ans, {"move": "Bb5+", "solutions": ["c4b5"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["Nxe5"]


def test_client_theme_and_flags_ignored():
    ans = answer_for(FEN_LEGAL, ["f3e5"], "TRAP")
    out = validate(ans, {"move": "Bb5+", "theme": "FORK", "result": "correct", "correct_move": "Bb5+"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["theme"] == "TRAP"


def test_invalid_stored_answer_fails_safe():
    assert validate({"fen": "junk", "solutions": ["e2e4"]}, {"move": "e4"}).result == AttemptResult.WRONG
    assert validate({"fen": FEN_LEGAL, "solutions": []}, {"move": "Nxe5"}).result == AttemptResult.WRONG


# --- Seed (independent verification) ---


def _independent(fen: str) -> dict[str, str]:
    board = chess.Board(fen)
    return {m.uci(): board.san(m) for m in board.legal_moves}


def test_seed_count_idempotent_no_dupes(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    fens = [p.answer_json["fen"] for p in puzzles]
    assert len(set(fens)) == 15


def test_seed_solutions_legal_and_tactical(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    multi = 0
    sides = set()
    themes = set()
    for puzzle in puzzles:
        stored = puzzle.answer_json
        legal = _independent(stored["fen"])
        for uci in stored["solutions"]:
            assert uci in legal  # every solution independently legal
        assert puzzle.position_json["side_to_move"] in ("white", "black")
        sides.add(puzzle.position_json["side_to_move"])
        themes.add(stored["theme"])
        assert puzzle.position_json["opening_fa"] and puzzle.position_json["trap_fa"]
        assert puzzle.position_json["theme_fa"] == THEME_FA[stored["theme"]]
        assert puzzle.position_json["mode"] == "tactic-1"
        if len(stored["solutions"]) > 1:
            multi += 1
        assert puzzle.prompt_fa and puzzle.explanation
        assert not puzzle.is_published and puzzle.status == "validated"
    assert multi >= 2  # several puzzles accept multiple tactics
    assert sides == {"white", "black"}
    assert len(themes) >= 5
    assert len({p.initial_rating for p in puzzles}) >= 5


def test_seed_no_leak_in_visible_payload(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    for puzzle in puzzles:
        assert puzzle.fen is None
        for key in ("fen", "solutions", "example", "correct_move", "answer_json"):
            assert key not in puzzle.position_json


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_api_list_hides_position_and_solutions(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    for entry in body:
        assert entry["fen"] is None
        assert "answer_json" not in entry
        assert entry["position_json"]["description_fa"]
        assert entry["position_json"]["opening_fa"]
        assert entry["position_json"]["trap_fa"]
    dumped = res.text
    for token in ("answer_json", "solutions", "correct_move", "rn1qkbnr", "r1bqkb1r"):
        assert token not in dumped


def test_api_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert res.json()["fen"] is None
    assert "answer_json" not in res.json()


def test_api_correct_wrong_malformed_submit(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    sans = solution_sans(puzzle.answer_json["fen"], puzzle.answer_json["solutions"])
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": sans[0]}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["correct_move"] == sans[0]

    if len(sans) > 1:
        alt = client.post(
            "/api/v1/attempts",
            json={"puzzle_id": puzzle.id, "answer": {"move": sans[1]}, "mode": "practice"},
            headers=headers,
        )
        assert alt.json()["result"] == "correct"

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "Ra1"}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    malformed = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "zzz"}, "mode": "practice"},
        headers=headers,
    )
    assert malformed.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": sans[0]}, "mode": "rated"},
    )
    assert rated.status_code == 401
