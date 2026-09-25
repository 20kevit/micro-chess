"""Blindfold Calculation (best move, eyes closed): description, eligibility, rules, seed, API."""

import chess
import pytest

from app.modules.blindfold_calculation import generator as gen_mod
from app.modules.blindfold_calculation import seed as seed_mod
from app.modules.blindfold_calculation.description import (
    describe_position,
    piece_count,
    side_to_move,
)
from app.modules.blindfold_calculation.validator import (
    SLUG,
    mating_sans,
    solution_san,
    validate,
)
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_generated_pool, publish_staged_puzzles

# Real puzzles.db row (first seed entry): Kd6.
FEN = "3k4/p7/2K5/3P2p1/1P3p2/P7/6P1/8 w - - 0 39"
SOLUTION = "c6d6"  # Kd6


def answer_for(fen: str = FEN, solution: str = SOLUTION) -> dict:
    return {"fen": fen, "solution": solution, "puzzle_id": "gjy0e", "rating": 1166.0}


def san_for(fen: str, uci: str) -> str:
    return chess.Board(fen).san(chess.Move.from_uci(uci))


# --- Eligibility (piece_count <= 12, single legal solution move) ---


def test_too_many_pieces_rejected():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"  # 32 pieces
    assert piece_count(fen) == 32
    assert gen_mod.question_for_row("x", fen, 1500, ["e2e4"]) is None


def test_exactly_twelve_pieces_accepted():
    fen = "R7/6pk/7p/4QP2/2q2K2/4P3/5R1P/6r1 w - - 5 51"  # 12 pieces
    assert piece_count(fen) == 12
    assert gen_mod.question_for_row("akJ2a", fen, 1598, ["e5e4"]) is not None


def test_illegal_first_move_rejected():
    assert gen_mod.question_for_row("x", FEN, 1000, ["a2a3"]) is None


def test_empty_line_rejected():
    assert gen_mod.question_for_row("x", FEN, 1000, []) is None


def test_invalid_fen_rejected():
    assert gen_mod.question_for_row("x", "not-a-fen", 1000, ["e2e4"]) is None


def test_only_first_move_is_the_answer():
    # The rest of the Lichess line is the forced continuation, not graded.
    data = gen_mod.question_for_row("x", FEN, 1000, [SOLUTION, "d8e8", "d6e6"])
    assert data is not None
    assert data["solution"] == SOLUTION
    assert data["solution_san"] == "Kd6"


# --- Description (structured Persian, deterministic) ---


def test_description_has_sections_and_turn():
    text = describe_position(FEN)
    lines = text.split("\n")
    assert lines[0] == "موقعیت مهره‌ها"
    assert "سفید" in lines
    assert "سیاه" in lines
    assert "نوبت: سفید" in text
    assert "نوبت: سیاه" in describe_position(
        "8/8/4R3/7k/p4P2/3pp1K1/r5P1/8 b - - 1 45"
    )


def test_description_piece_order_and_names():
    fen = "r1bqk2r/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w Kkq - 0 1"
    text = describe_position(fen)
    for word in ("شاه", "وزیر", "رخ", "فیل", "اسب", "پیاده"):
        assert word in text
    assert "سرباز" not in text
    white = text.split("سیاه")[0]
    positions = [white.index(w) for w in ("شاه:", "وزیر:", "رخ:", "فیل:", "اسب:", "پیاده:")]
    assert positions == sorted(positions)


def test_description_omits_empty_types():
    text = describe_position(FEN)  # kings + pawns only
    assert "وزیر:" not in text
    assert "رخ:" not in text
    assert "فیل:" not in text
    assert "اسب:" not in text


def test_description_squares_in_chessboard_order():
    text = describe_position(FEN)
    assert text.index("a3") < text.index("b4") < text.index("d5") < text.index("g2")


def test_description_coordinates_rendered_ltr():
    assert "c6" in describe_position(FEN)
    assert "d8" in describe_position(FEN)


def test_description_castling_and_ep_communicated():
    text = describe_position("r3k2r/8/8/8/3pP3/8/8/R3K2R w KQkq e3 0 1")
    assert "قلعه:" in text
    assert "آنپاسان: e3" in text


def test_description_no_special_lines_for_dash():
    text = describe_position(FEN)
    assert "قلعه" not in text
    assert "آنپاسان" not in text


def test_description_deterministic():
    assert describe_position(FEN) == describe_position(FEN)


def test_description_invalid_fen_raises():
    with pytest.raises(ValueError):
        describe_position("not-a-fen")


def test_side_to_move():
    assert side_to_move(FEN) == "white"
    assert side_to_move("8/8/4R3/7k/p4P2/3pp1K1/r5P1/8 b - - 1 45") == "black"


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Validator: authoritative SAN parsing + exact solution match ---


def test_correct_move_accepted():
    assert validate(answer_for(), {"move": "Kd6"}).result == AttemptResult.CORRECT


def test_check_suffix_variants_accepted():
    # SAN identity is the move, not the string: suffixes never matter.
    assert validate(answer_for(), {"move": "Kd6+"}).result == AttemptResult.CORRECT
    assert validate(answer_for(), {"move": "Kd6#"}).result == AttemptResult.CORRECT


def test_whitespace_tolerated():
    assert validate(answer_for(), {"move": "  Kd6  "}).result == AttemptResult.CORRECT


def test_legal_but_wrong_move_rejected():
    out = validate(answer_for(), {"move": "Kc5"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["correct_move"] == "Kd6"
    assert out.detail["missed"] == ["Kd6"]


def test_illegal_move_rejected():
    assert validate(answer_for(), {"move": "Ke99"}).result == AttemptResult.WRONG
    assert validate(answer_for(), {"move": "Qh7#"}).result == AttemptResult.WRONG


def test_malformed_san_rejected():
    for bad in ("zzz", "", "   ", "Q", "e9", 123, None):
        assert validate(answer_for(), {"move": bad}).result == AttemptResult.WRONG


def test_capture_and_promotion_solutions():
    assert (
        validate(
            answer_for("6R1/5p2/1p2p3/p6Q/4k3/q4r2/P7/K4R2 w - - 6 43", "f1f3"),
            {"move": "Rxf3"},
        ).result
        == AttemptResult.CORRECT
    )
    assert (
        validate(
            answer_for("6R1/4Pkp1/7p/5p2/8/P4PK1/4rP2/8 w - - 3 37", "e7e8q"),
            {"move": "e8=Q+"},
        ).result
        == AttemptResult.CORRECT
    )


def test_correct_detail_carries_canonical_move():
    out = validate(answer_for(), {"move": "Kd6+"})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["correct_move"] == "Kd6"
    assert out.detail["correct"] == ["Kd6"]


def test_solution_san_helper():
    assert solution_san(FEN, SOLUTION) == "Kd6"


# --- Security: server is authoritative, client data ignored ---


def test_client_fen_ignored():
    out = validate(answer_for(), {"move": "Kd6", "fen": "8/8/8/8/8/8/8/8 w - - 0 1"})
    assert out.result == AttemptResult.CORRECT


def test_client_solution_ignored():
    out = validate(answer_for(), {"move": "Kc5", "solution": "c5c4", "correct_move": "Kc5"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["Kd6"]


def test_fake_correctness_metadata_rejected():
    out = validate(answer_for(), {"move": "Kc5", "result": "correct", "score": 99})
    assert out.result == AttemptResult.WRONG


def test_invalid_stored_fen_fails_safe():
    assert validate({"fen": "junk", "solution": SOLUTION}, {"move": "Kd6"}).result == AttemptResult.WRONG


# --- Legacy mate-in-1 rows keep their original rule ---


def test_legacy_mate_accepted():
    fen = "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"  # Rxe8#
    assert mating_sans(fen) == ["Rxe8#"]
    legacy = {"fen": fen, "example": "Rxe8#", "mate_count": 1}
    assert validate(legacy, {"move": "Rxe8#"}).result == AttemptResult.CORRECT
    assert validate(legacy, {"move": "Rxe8"}).result == AttemptResult.CORRECT


def test_legacy_non_mating_move_rejected():
    legacy = {"fen": "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", "example": "Rxe8#", "mate_count": 1}
    out = validate(legacy, {"move": "Re2"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["correct_move"] == "Rxe8#"


# --- Seed (independent verification) ---


def test_seed_count_idempotent_shapes(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    sides = set()
    for puzzle in puzzles:
        # No position leak: fen column empty, no FEN/solution in visible payload.
        assert puzzle.fen is None
        assert puzzle.position_json["mode"] == "best-move"
        assert puzzle.position_json["side_to_move"] in ("white", "black")
        assert puzzle.position_json["piece_count"] <= 12
        assert "fen" not in puzzle.position_json
        assert "solution" not in puzzle.position_json
        sides.add(puzzle.position_json["side_to_move"])
        stored = puzzle.answer_json
        board = chess.Board(stored["fen"])
        count = sum(1 for sq in chess.SQUARES if board.piece_at(sq) is not None)
        assert count <= 12
        assert chess.Move.from_uci(stored["solution"]) in board.legal_moves
        assert puzzle.prompt_fa == "بهترین حرکت چیست؟"
        assert puzzle.explanation
        assert not puzzle.is_published and puzzle.status == "validated"
        # Validator agrees with the stored solution.
        assert validate(stored, {"move": board.san(chess.Move.from_uci(stored["solution"]))}).result == AttemptResult.CORRECT
    assert sides == {"white", "black"}


def test_seed_archives_legacy_rows(db_session):
    from app.modules.exercises.models import Exercise

    db_session.add(
        Exercise(
            slug=SLUG,
            title_fa="x",
            title_en="y",
            description="z",
            is_active=True,
            sort_order=14,
        )
    )
    legacy = Puzzle(
        exercise_slug=SLUG,
        fen=None,
        position_json={"description_fa": "old", "side_to_move": "white", "mode": "mate-in-1"},
        answer_json={"fen": "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", "example": "Rxe8#", "mate_count": 1},
        prompt_fa="old",
        is_published=True,
        is_archived=False,
    )
    db_session.add(legacy)
    db_session.commit()
    assert seed_mod.seed_db(db_session) == 15
    db_session.refresh(legacy)
    assert legacy.is_archived is True  # archived, never hard-deleted
    current = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False)  # noqa: E712
        .all()
    )
    assert len(current) == 15
    assert all(p.answer_json.get("solution") for p in current)


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def _correct_san(puzzle: Puzzle) -> str:
    board = chess.Board(puzzle.answer_json["fen"])
    return board.san(chess.Move.from_uci(puzzle.answer_json["solution"]))


def test_api_list_hides_answer_and_fen(client, db_session):
    _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    for entry in body:
        assert entry["fen"] is None
        assert "answer_json" not in entry
        assert entry["position_json"]["description_fa"]
        assert "نوبت:" in entry["position_json"]["description_fa"]
        assert entry["position_json"]["side_to_move"] in ("white", "black")
    dumped = res.text
    assert "answer_json" not in dumped


def test_api_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert res.json()["fen"] is None
    assert "answer_json" not in res.json()


@pytest.fixture
def calculation_source_db(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "puzzles.db"
    connection = sqlite3.connect(path)
    connection.execute(
        'CREATE TABLE "puzzles" ("PuzzleId" TEXT, "FEN" TEXT, "Rating" INTEGER, "Themes" TEXT, "Moves" TEXT)'
    )
    rows = [
        (item["puzzle_id"], item["fen"], item["rating"], "", item["solution"])
        for item in seed_mod.PUZZLES
    ]
    rows.extend(
        [
            ("extra-1", "4k3/8/8/8/8/8/8/4K3 w - - 0 1", 1200, "", "e1d1"),
            ("extra-2", "4k3/8/8/8/8/8/8/3K4 w - - 0 1", 1200, "", "d1c1"),
            ("extra-3", "4k3/8/8/8/8/8/8/2K5 w - - 0 1", 1200, "", "c1b1"),
            ("extra-4", "4k3/8/8/8/8/8/8/1K6 w - - 0 1", 1200, "", "b1a1"),
            ("extra-5", "4k3/8/8/8/8/8/8/5K2 w - - 0 1", 1200, "", "f1e1"),
        ]
    )
    connection.executemany(
        'INSERT INTO "puzzles" ("PuzzleId", "FEN", "Rating", "Themes", "Moves") VALUES (?, ?, ?, ?, ?)',
        rows,
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("PUZZLES_DB_PATH", str(path))


@pytest.fixture
def published_pool(db_session, calculation_source_db):
    seed_mod.seed_db(db_session)
    publish_generated_pool(db_session, SLUG, gen_mod.create_puzzle)


def test_api_next_hides_solution(client, db_session, published_pool):
    res = client.post("/api/v1/blindfold-calculation/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] is None
    assert "answer_json" not in body
    assert "نوبت:" in body["position_json"]["description_fa"]


def test_api_correct_and_wrong_submit(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"move": _correct_san(puzzle)},
            "mode": "practice",
        },
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["correct_move"] == _correct_san(puzzle)
    # Practice attempts never set rating_delta (rating stub rule).
    assert ok.json()["rating_delta"] is None

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "zzz"}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"
    assert bad.json()["score"] == 0.0

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "zzz"}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_speed_lifecycle(client, db_session, published_pool):
    headers = make_auth_headers(db_session)
    started = client.post("/api/v1/blindfold-calculation/sessions", json={})
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    buf = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/puzzles", json={"count": 20}
    )
    assert buf.status_code == 200
    assert len(buf.json()) == 20
    for entry in buf.json():
        assert "answer_json" not in entry
        assert entry["fen"] is None
    clock = client.post(f"/api/v1/blindfold-calculation/sessions/{session_id}/start")
    assert clock.status_code == 200
    first = buf.json()[0]
    stored = db_session.get(Puzzle, first["id"])
    assert stored is not None
    correct = _correct_san(stored)
    sub = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"move": correct}},
        headers=headers,
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    assert sub.json()["attempt"]["score"] == 1.0
    # A legal but incorrect move is wrong.
    board = chess.Board(stored.answer_json["fen"])
    solution_uci = stored.answer_json["solution"]
    other = next(m.uci() for m in board.legal_moves if m.uci() != solution_uci)
    other_san = board.san(chess.Move.from_uci(other))
    second = buf.json()[1]
    stored2 = db_session.get(Puzzle, second["id"])
    assert stored2 is not None
    if stored2.answer_json["solution"] != other:
        bad = client.post(
            f"/api/v1/blindfold-calculation/sessions/{session_id}/submit",
            json={"puzzle_id": second["id"], "answer": {"move": other_san}},
            headers=headers,
        )
        # Either correct (same solution) or wrong — never a crash.
        assert bad.json()["attempt"]["result"] in ("correct", "wrong")
    report = client.get(f"/api/v1/blindfold-calculation/sessions/{session_id}/report")
    assert report.status_code == 200
    assert report.json()["session"]["attempted"] >= 1
    for entry in report.json()["entries"]:
        assert entry["fen"] is None  # blindfold: positions never leak, even post-submit


def test_speed_submit_before_start_rejected(client, db_session, published_pool):
    started = client.post("/api/v1/blindfold-calculation/sessions", json={})
    session_id = started.json()["session_id"]
    buf = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/puzzles", json={"count": 20}
    )
    first = buf.json()[0]
    sub = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"move": "Kd6"}},
        headers=make_auth_headers(db_session),
    )
    assert sub.status_code == 409  # session_not_started


def test_speed_timeout_rejected(client, db_session, published_pool):
    from datetime import datetime, timedelta, timezone

    from app.modules.blindfold_calculation.models import BlindfoldCalculationSpeedSession

    started = client.post("/api/v1/blindfold-calculation/sessions", json={})
    session_id = started.json()["session_id"]
    buf = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/puzzles", json={"count": 20}
    )
    assert buf.status_code == 200
    clock = client.post(f"/api/v1/blindfold-calculation/sessions/{session_id}/start")
    assert clock.status_code == 200
    # Force expiry server-side (the client clock is never trusted).
    session = db_session.get(BlindfoldCalculationSpeedSession, session_id)
    assert session is not None
    session.ends_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()
    first = buf.json()[0]
    late = client.post(
        f"/api/v1/blindfold-calculation/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"move": "Kd6"}},
        headers=make_auth_headers(db_session),
    )
    assert late.status_code == 410
