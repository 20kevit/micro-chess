"""Memorization Board (Exercise 12, صفحه‌ی حفظی): extraction, timing, matching,
scoring, generator, seed, API, and speed sessions."""

import random

import pytest

from app.modules.chinese_board import generator as gen_mod
from app.modules.chinese_board import pieces as cb
from app.modules.chinese_board import seed as seed_mod
from app.modules.chinese_board.scoring import score_chinese_board
from app.modules.chinese_board.validator import SLUG, normalize_entry, validate
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult

FOUR_PIECE_FEN = "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1"

FOUR_PIECES = [
    {"square": "e8", "piece": "K", "color": "black"},
    {"square": "d8", "piece": "Q", "color": "black"},
    {"square": "d1", "piece": "Q", "color": "white"},
    {"square": "e1", "piece": "K", "color": "white"},
]

TEN_PIECE_FEN = "4k1r1/pppp4/8/8/8/8/PP6/R3K3 w - - 0 1"

TEN_PIECES = [
    {"square": "e8", "piece": "K", "color": "black"},
    {"square": "g8", "piece": "R", "color": "black"},
    {"square": "a7", "piece": "P", "color": "black"},
    {"square": "b7", "piece": "P", "color": "black"},
    {"square": "c7", "piece": "P", "color": "black"},
    {"square": "d7", "piece": "P", "color": "black"},
    {"square": "a1", "piece": "R", "color": "white"},
    {"square": "e1", "piece": "K", "color": "white"},
    {"square": "a2", "piece": "P", "color": "white"},
    {"square": "b2", "piece": "P", "color": "white"},
]


def answer_for_fen(fen: str) -> dict:
    return {"fen": fen}


def attempt(pieces: object) -> dict:
    return {"pieces": pieces}


# --- Piece extraction ---


def test_extract_every_piece_with_color_type_square():
    pieces = cb.extract_pieces(FOUR_PIECE_FEN)
    assert len(pieces) == 4
    by_square = {p["square"]: p for p in pieces}
    assert by_square["e8"] == {"color": "black", "type": "K", "square": "e8"}
    assert by_square["d8"] == {"color": "black", "type": "Q", "square": "d8"}
    assert by_square["d1"] == {"color": "white", "type": "Q", "square": "d1"}
    assert by_square["e1"] == {"color": "white", "type": "K", "square": "e1"}


def test_extract_all_kinds_and_pawns():
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    pieces = cb.extract_pieces(fen)
    kinds = {p["type"] for p in pieces}
    assert kinds == {"K", "Q", "R", "B", "N", "P"}
    colors = {p["color"] for p in pieces}
    assert colors == {"white", "black"}
    assert len(pieces) == cb.piece_count(fen)


def test_extract_agrees_with_python_chess():
    import chess

    fen = "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12"
    board = chess.Board(fen)
    pieces = cb.extract_pieces(fen)
    assert len(pieces) == len(board.piece_map())
    for p in pieces:
        piece = board.piece_at(chess.parse_square(p["square"]))
        assert piece is not None
        assert piece.symbol().upper() == p["type"]
        assert ("white" if piece.color == chess.WHITE else "black") == p["color"]


def test_extract_invalid_fen_raises():
    with pytest.raises(ValueError):
        cb.extract_pieces("not a fen")


def test_startpos_has_32_pieces():
    assert cb.piece_count("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1") == 32


# --- Piece count + memorization time ---


def test_piece_count_counts_every_piece_once():
    assert cb.piece_count(FOUR_PIECE_FEN) == 4
    assert cb.piece_count(TEN_PIECE_FEN) == 10


def test_memorization_time_is_count_times_1000ms():
    assert cb.memorization_ms(FOUR_PIECE_FEN) == 4000
    assert cb.memorization_ms(TEN_PIECE_FEN) == 10000
    assert cb.MEMORIZE_MS_PER_PIECE == 1000
    # Spec examples: 5 pieces -> 5s, 8 -> 8s, 10 -> 10s, 15 -> 15s.
    assert 5 * cb.MEMORIZE_MS_PER_PIECE == 5000
    assert 8 * cb.MEMORIZE_MS_PER_PIECE == 8000
    assert 10 * cb.MEMORIZE_MS_PER_PIECE == 10000
    assert 15 * cb.MEMORIZE_MS_PER_PIECE == 15000


def test_fen_metadata_does_not_change_count_or_budget():
    # Same placement, different side/castling/clocks: identical budget.
    a = "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1"
    b = "3qk3/8/8/8/8/8/8/3QK3 b KQkq e3 14 39"
    assert cb.piece_count(a) == cb.piece_count(b) == 4
    assert cb.memorization_ms(a) == cb.memorization_ms(b) == 4000


# --- Entry normalization ---


def test_normalize_entry_accepts_case_variants():
    assert normalize_entry({"square": "E4", "piece": "q", "color": "White"}) == ("white", "Q", "e4")


def test_normalize_entry_rejects_malformed():
    assert normalize_entry({"square": "e9", "piece": "Q", "color": "white"}) is None
    assert normalize_entry({"square": "e4", "piece": "X", "color": "white"}) is None
    assert normalize_entry({"square": "e4", "piece": "Q", "color": "green"}) is None
    assert normalize_entry({"square": "e4", "piece": "Q"}) is None
    assert normalize_entry("e4") is None
    assert normalize_entry(None) is None


# --- Exact matching ---


def test_perfect_reconstruction_is_correct():
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(list(FOUR_PIECES)))
    assert out.result == AttemptResult.CORRECT
    assert len(out.detail["correct"]) == 4
    assert out.detail["missing"] == []
    assert out.detail["extra"] == []
    assert out.detail["piece_count"] == 4
    assert out.detail["memorization_ms"] == 4000


def test_order_does_not_matter():
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(list(reversed(FOUR_PIECES))))
    assert out.result == AttemptResult.CORRECT


def test_ten_piece_perfect_scores_50():
    out = validate(answer_for_fen(TEN_PIECE_FEN), attempt(list(TEN_PIECES)))
    assert out.result == AttemptResult.CORRECT
    assert score_chinese_board(out) == 50.0


def test_empty_submission_is_all_missing():
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt([]))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["missing"]) == 4
    assert score_chinese_board(out) == -8.0


# --- Wrong square: one error, never double-counted ---


def test_wrong_square_is_single_error():
    moved = [dict(p, square="e7") if p["square"] == "e8" else p for p in FOUR_PIECES]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(moved))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["correct"]) == 3
    # Exactly one wrong piece — NOT a missing plus an extra.
    assert len(out.detail["wrong"]) == 1
    assert out.detail["missing"] == []
    assert out.detail["extra"] == []
    assert score_chinese_board(out) == 3 * 5 - 2  # 13


def test_wrong_color_is_not_an_exact_match():
    recolored = [dict(p, color="white") if p["square"] == "e8" else p for p in FOUR_PIECES]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(recolored))
    assert out.result == AttemptResult.WRONG
    # Black king missing, extra white king: two errors (different kind keys).
    assert out.detail["missing"] == ["black:K@e8"]
    assert out.detail["extra"] == ["white:K@e8"]
    assert score_chinese_board(out) == 3 * 5 - 2 * 2  # 11


def test_wrong_type_is_not_an_exact_match():
    retyped = [dict(p, piece="R") if p["square"] == "d8" else p for p in FOUR_PIECES]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(retyped))
    assert out.result == AttemptResult.WRONG
    assert out.detail["missing"] == ["black:Q@d8"]
    assert out.detail["extra"] == ["black:R@d8"]
    assert score_chinese_board(out) == 3 * 5 - 2 * 2  # 11


# --- Missing / extra ---


def test_one_missing_scores_43_of_50():
    dropped = [p for p in TEN_PIECES if p["square"] != "a7"]
    out = validate(answer_for_fen(TEN_PIECE_FEN), attempt(dropped))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["correct"]) == 9
    assert out.detail["missing"] == ["black:P@a7"]
    assert score_chinese_board(out) == 9 * 5 - 2  # 43


def test_one_extra_scores_48_of_50():
    plus = list(TEN_PIECES) + [{"square": "h4", "piece": "N", "color": "white"}]
    out = validate(answer_for_fen(TEN_PIECE_FEN), attempt(plus))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["correct"]) == 10
    assert out.detail["extra"] == ["white:N@h4"]
    assert score_chinese_board(out) == 10 * 5 - 2  # 48


def test_mixed_correct_wrong_missing_extra():
    # 10 originals: keep 8 exact, move 1 (wrong), drop 1 (missing), add 1 (extra).
    user = [p for p in TEN_PIECES if p["square"] not in ("b7", "g8")]
    user.append({"square": "g7", "piece": "R", "color": "black"})  # g8 rook -> g7
    user.append({"square": "h4", "piece": "N", "color": "white"})  # extra
    out = validate(answer_for_fen(TEN_PIECE_FEN), attempt(user))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["correct"]) == 8
    assert len(out.detail["wrong"]) == 2  # wrong pair + extra (disjoint, no double count)
    assert len(out.detail["missing"]) == 1
    assert len(out.detail["extra"]) == 1
    assert score_chinese_board(out) == 8 * 5 - 2 * (2 + 1)  # 34


def test_duplicate_piece_types_match_sensibly():
    # Three white pawns: two exact, one shifted -> single wrong error.
    fen = "4k3/8/8/8/8/8/PPP5/4K3 w - - 0 1"
    user = [
        {"square": "a2", "piece": "P", "color": "white"},
        {"square": "b2", "piece": "P", "color": "white"},
        {"square": "d2", "piece": "P", "color": "white"},  # c2 pawn -> d2
        {"square": "e1", "piece": "K", "color": "white"},
        {"square": "e8", "piece": "K", "color": "black"},
    ]
    out = validate(answer_for_fen(fen), attempt(user))
    assert out.result == AttemptResult.WRONG
    assert len(out.detail["correct"]) == 4
    assert len(out.detail["wrong"]) == 1
    assert out.detail["missing"] == []
    assert out.detail["extra"] == []
    assert score_chinese_board(out) == 4 * 5 - 2  # 18


def test_kings_count_as_pieces():
    # Dropping both kings is two missing errors.
    user = [p for p in FOUR_PIECES if p["piece"] != "K"]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(user))
    assert len(out.detail["correct"]) == 2
    assert len(out.detail["missing"]) == 2
    assert score_chinese_board(out) == 2 * 5 - 2 * 2  # 6


# --- Malformed input fails safe ---


def test_malformed_entries_are_wrong_never_crash():
    bad_inputs = [
        {},
        {"pieces": "nope"},
        {"pieces": [{"square": "e4", "piece": "Q"}]},
        {"pieces": [{"square": "e4", "piece": "Q", "color": "white", "extra": 1}]},
        {"pieces": None},
        None,
        "pieces",
    ]
    for bad in bad_inputs:
        out = validate(answer_for_fen(FOUR_PIECE_FEN), bad)  # type: ignore[arg-type]
        assert out.result == AttemptResult.WRONG


def test_duplicate_square_is_wrong():
    dup = list(FOUR_PIECES) + [{"square": "e1", "piece": "P", "color": "white"}]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(dup))
    assert out.result == AttemptResult.WRONG


def test_invalid_stored_fen_is_wrong():
    out = validate({"fen": "bad fen"}, attempt(list(FOUR_PIECES)))
    assert out.result == AttemptResult.WRONG
    assert validate({}, attempt(list(FOUR_PIECES))).result == AttemptResult.WRONG


# --- Scoring ---


def test_negative_scores_allowed_no_floor():
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt([]))
    assert score_chinese_board(out) == -8.0
    # All wrong colors/types: 0 correct, 4 missing + 4 extra.
    user = [
        {"square": "a1", "piece": "P", "color": "white"},
        {"square": "a2", "piece": "P", "color": "white"},
        {"square": "a3", "piece": "P", "color": "white"},
        {"square": "a4", "piece": "P", "color": "white"},
    ]
    out = validate(answer_for_fen(FOUR_PIECE_FEN), attempt(user))
    assert score_chinese_board(out) == 0 * 5 - 2 * (4 + 4)  # -16


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Server authority ---


def test_client_cannot_forge_score_or_counts():
    out = validate(
        answer_for_fen(FOUR_PIECE_FEN),
        {
            "pieces": [],
            "score": 100.0,
            "correct": ["everything"],
            "piece_count": 0,
            "original_fen": FOUR_PIECE_FEN,
        },
    )
    assert out.result == AttemptResult.WRONG
    assert score_chinese_board(out) == -8.0
    assert out.detail["piece_count"] == 4


def test_client_fen_ignored_answer_comes_from_store():
    other = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
    out = validate(
        answer_for_fen(FOUR_PIECE_FEN),
        {"pieces": [], "fen": other},
    )
    assert out.detail["piece_count"] == 4
    assert len(out.detail["missing"]) == 4


# --- Generator ---


def test_question_for_fen_computes_budget():
    data = gen_mod.question_for_fen(TEN_PIECE_FEN)
    assert data is not None
    assert data["piece_count"] == 10
    assert data["memorization_ms"] == 10000
    assert data["fen"] == TEN_PIECE_FEN


def test_question_for_fen_rejects_invalid():
    assert gen_mod.question_for_fen("not a fen") is None


def test_generated_puzzles_come_from_db_with_server_budget(db_session):
    rng = random.Random(1234)
    for _ in range(10):
        puzzle = gen_mod.create_puzzle(db_session, rng)
        assert puzzle.fen
        assert puzzle.answer_json == {"fen": puzzle.fen}
        position = puzzle.position_json
        assert position["fen"] == puzzle.fen
        assert position["piece_count"] == cb.piece_count(puzzle.fen)
        assert position["memorization_ms"] == position["piece_count"] * 1000


def test_generator_never_leaks_answer_fields(db_session):
    rng = random.Random(7)
    puzzle = gen_mod.create_puzzle(db_session, rng)
    assert "correct" not in puzzle.position_json
    assert "pieces" not in puzzle.position_json


# --- Seed ---


def test_seed_is_deterministic_and_idempotent(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15


def test_seed_puzzles_valid_with_rising_sizes(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    counts = []
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.answer_json == {"fen": puzzle.fen}
        count = cb.piece_count(puzzle.fen)
        counts.append(count)
        assert puzzle.position_json["piece_count"] == count
        assert puzzle.position_json["memorization_ms"] == count * 1000
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        pieces = [{"square": p["square"], "piece": p["type"], "color": p["color"]}
                  for p in cb.extract_pieces(puzzle.fen)]
        assert validate(puzzle.answer_json, {"pieces": pieces}).result == AttemptResult.CORRECT
    assert min(counts) <= 8
    assert max(counts) >= 24


def test_seed_rejects_broken_puzzles():
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"fen": "bad"})
    with pytest.raises(ValueError):
        seed_mod.verify_puzzle({"fen": "8/8/8/8/8/8/8/8 w - - 0 1"})


# --- API ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_api_list_hides_answer(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    assert body[0]["fen"]
    assert body[0]["position_json"]["fen"] == body[0]["fen"]
    assert body[0]["position_json"]["memorization_ms"] == body[0]["position_json"]["piece_count"] * 1000


def test_api_next_hides_answer(client, db_session):
    res = client.post("/api/v1/chinese-board/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    assert body["fen"]
    assert body["position_json"]["memorization_ms"] == body["position_json"]["piece_count"] * 1000
    assert "correct" not in body["position_json"]
    assert "pieces" not in body["position_json"]


def test_api_next_varies_across_calls(client, db_session):
    seen = set()
    for _ in range(8):
        res = client.post("/api/v1/chinese-board/next", json={})
        assert res.status_code == 200
        seen.add(res.json()["fen"])
    # Real-database sampling serves varied positions (seeded rows excluded
    # from this check only by probability; variety must exceed one).
    assert len(seen) > 1


def test_api_submit_perfect_and_scored(client, db_session):
    puzzle = _seeded(db_session)
    pieces = [{"square": p["square"], "piece": p["type"], "color": p["color"]}
              for p in cb.extract_pieces(puzzle.fen)]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": pieces}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 5.0 * len(pieces)


def test_api_submit_partial_reconstruction_scored(client, db_session):
    puzzle = _seeded(db_session)
    pieces = [{"square": p["square"], "piece": p["type"], "color": p["color"]}
              for p in cb.extract_pieces(puzzle.fen)]
    dropped = pieces[:-1]
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"pieces": dropped}, "mode": "practice"},
    )
    assert res.status_code == 200
    assert res.json()["result"] == "wrong"
    assert res.json()["score"] == 5.0 * len(dropped) - 2.0


def test_api_submit_ignores_forged_score(client, db_session):
    puzzle = _seeded(db_session)
    res = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"pieces": [], "score": 999, "correct_count": 99},
            "mode": "practice",
        },
    )
    assert res.status_code == 200
    assert res.json()["score"] != 999
    assert res.json()["score"] == -2.0 * cb.piece_count(puzzle.fen)


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_speed_lifecycle(client, db_session):
    started = client.post("/api/v1/chinese-board/sessions", json={})
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    buf = client.post(f"/api/v1/chinese-board/sessions/{session_id}/puzzles", json={"count": 20})
    assert buf.status_code == 200
    assert len(buf.json()) == 20
    for entry in buf.json():
        assert "answer_json" not in entry
        assert entry["position_json"]["memorization_ms"] > 0
    clock = client.post(f"/api/v1/chinese-board/sessions/{session_id}/start")
    assert clock.status_code == 200
    first = buf.json()[0]
    pieces = [{"square": p["square"], "piece": p["type"], "color": p["color"]}
              for p in cb.extract_pieces(first["fen"])]
    sub = client.post(
        f"/api/v1/chinese-board/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"pieces": pieces}},
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    report = client.get(f"/api/v1/chinese-board/sessions/{session_id}/report")
    assert report.status_code == 200
    assert report.json()["session"]["attempted"] == 1
    assert report.json()["entries"][0]["fen"] == first["fen"]


def test_speed_submit_rejects_forged_answer(client, db_session):
    started = client.post("/api/v1/chinese-board/sessions", json={})
    session_id = started.json()["session_id"]
    buf = client.post(f"/api/v1/chinese-board/sessions/{session_id}/puzzles", json={"count": 20})
    client.post(f"/api/v1/chinese-board/sessions/{session_id}/start")
    first = buf.json()[0]
    # Forged score/count fields are ignored; empty reconstruction still fails.
    sub = client.post(
        f"/api/v1/chinese-board/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"pieces": [], "score": 500}},
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "wrong"
    assert sub.json()["attempt"]["score"] != 500
