"""Blindfold Calculation (Mate in 1): description, mate rules, seed, API."""

import chess
import pytest

from app.modules.blindfold_calculation import seed as seed_mod
from app.modules.blindfold_calculation.description import describe_position, side_to_move
from app.modules.blindfold_calculation.validator import SLUG, mating_moves, mating_sans, validate
from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult

FEN_ROOK = "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"  # Rxe8#
FEN_KNIGHT = "6rk/6pp/8/4N3/8/8/8/6K1 w - - 0 1"  # Nf7#
FEN_BISHOP = "k7/p7/8/8/B7/8/8/1R4K1 w - - 0 1"  # Bc6#
FEN_PAWN = "6bk/6pp/5P2/7N/8/8/8/6K1 w - - 0 1"  # fxg7#
FEN_BLACK = "6k1/8/8/8/8/3b1b2/4rPPP/6K1 b - - 0 1"  # ...Re1#


def answer_for(fen: str) -> dict:
    return {"fen": fen, "example": mating_sans(fen)[0], "mate_count": 1}


# --- Description ---


def test_description_side_to_move_white():
    assert describe_position(FEN_ROOK).startswith("نوبت سفید است.")
    assert side_to_move(FEN_ROOK) == "white"


def test_description_side_to_move_black():
    assert describe_position(FEN_BLACK).startswith("نوبت سیاه است.")
    assert side_to_move(FEN_BLACK) == "black"


def test_description_piece_names_and_colors():
    text = describe_position(FEN_KNIGHT)
    for word in ("شاه", "رخ", "اسب", "سرباز", "سفید", "سیاه"):
        assert word in text


def test_description_all_piece_types():
    fen = "r1bqk2r/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w Kkq - 0 1"
    text = describe_position(fen)
    for word in ("شاه", "وزیر", "رخ", "فیل", "اسب", "سرباز"):
        assert word in text


def test_description_order_white_then_black_king_first():
    text = describe_position(FEN_KNIGHT)
    assert text.index("مهره‌های سفید") < text.index("مهره‌های سیاه")
    assert text.index("شاه در g1") < text.index("اسب در e5")
    assert text.index("شاه در h8") < text.index("رخ در g8")


def test_description_squares_sorted_within_type():
    text = describe_position(FEN_ROOK)
    assert text.index("f7") < text.index("g7") < text.index("h7")


def test_description_coordinates_rendered_ltr():
    assert "e1" in describe_position(FEN_ROOK)
    assert "h8" in describe_position(FEN_KNIGHT)


def test_description_sparse_position():
    text = describe_position("7k/8/8/8/8/8/8/6K1 w - - 0 1")
    assert "شاه در h8" in text and "شاه در g1" in text


def test_description_no_castling_note_for_dash():
    assert "قلعه" not in describe_position(FEN_ROOK)


def test_description_castling_note_when_present():
    text = describe_position("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert "قلعه" in text


def test_description_deterministic():
    assert describe_position(FEN_ROOK) == describe_position(FEN_ROOK)


def test_description_invalid_fen_raises():
    with pytest.raises(ValueError):
        describe_position("not-a-fen")


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Mate detection ---


def test_mating_moves_single():
    assert mating_moves(FEN_ROOK) == ["e1e8"]
    assert mating_sans(FEN_ROOK) == ["Rxe8#"]


def test_valid_mate_accepted():
    assert validate(answer_for(FEN_ROOK), {"move": "Rxe8#"}).result == AttemptResult.CORRECT


def test_non_mating_legal_move_rejected():
    out = validate(answer_for(FEN_ROOK), {"move": "Re2"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["correct_move"] == "Rxe8#"


def test_illegal_move_rejected():
    assert validate(answer_for(FEN_ROOK), {"move": "Ke2"}).result == AttemptResult.WRONG


def test_malformed_san_rejected():
    for bad in ("zzz", "", "   ", "Q", "e9", 123, None):
        assert validate(answer_for(FEN_ROOK), {"move": bad}).result == AttemptResult.WRONG


def test_fake_hash_suffix_rejected():
    # Qh7# is well-formed SAN but not mate here.
    out = validate(answer_for(FEN_ROOK), {"move": "Qh7#"})
    assert out.result == AttemptResult.WRONG


def test_capture_mate():
    assert validate(answer_for(FEN_PAWN), {"move": "fxg7#"}).result == AttemptResult.CORRECT


def test_queen_mate():
    assert validate(answer_for("6k1/6pp/6Q1/8/8/8/8/6K1 w - - 0 1"), {"move": "Qe8#"}).result == AttemptResult.CORRECT


def test_rook_mate():
    assert validate(answer_for(FEN_ROOK), {"move": "Rxe8#"}).result == AttemptResult.CORRECT


def test_bishop_mate():
    assert validate(answer_for(FEN_BISHOP), {"move": "Bc6#"}).result == AttemptResult.CORRECT


def test_knight_mate():
    assert validate(answer_for(FEN_KNIGHT), {"move": "Nf7#"}).result == AttemptResult.CORRECT


def test_black_to_move_mate():
    out = validate(answer_for(FEN_BLACK), {"move": "Re1#"})
    assert out.result == AttemptResult.CORRECT


def test_promotion_san_parses_where_legal():
    # Promotion notation is supported by the SAN parser (no promotion in seed).
    board = chess.Board("7k/4P3/8/8/8/8/8/6K1 w - - 0 1")
    move = board.parse_san("e8=Q")
    assert move.uci() == "e7e8q"


# --- Answer normalization ---


def test_whitespace_tolerated():
    assert validate(answer_for(FEN_ROOK), {"move": "  Rxe8#  "}).result == AttemptResult.CORRECT


def test_hash_suffix_optional():
    assert validate(answer_for(FEN_ROOK), {"move": "Rxe8"}).result == AttemptResult.CORRECT


def test_check_suffix_optional():
    assert validate(answer_for(FEN_KNIGHT), {"move": "Nf7+"}).result == AttemptResult.CORRECT


def test_empty_and_wrong():
    assert validate(answer_for(FEN_ROOK), {"move": ""}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN_ROOK), {"move": "Ra1"}).result == AttemptResult.WRONG
    assert validate(answer_for(FEN_ROOK), {}).result == AttemptResult.WRONG


def test_alternative_mate_accepted_when_several_exist():
    # Validator correctness = legal + checkmate, not string equality.
    fen = "6k1/5ppp/8/3Q4/8/8/5PPP/6K1 w - - 0 1"  # Qa8# and Qd8#
    assert len(mating_sans(fen)) == 2
    assert validate({"fen": fen}, {"move": "Qa8#"}).result == AttemptResult.CORRECT
    assert validate({"fen": fen}, {"move": "Qd8#"}).result == AttemptResult.CORRECT


def test_correct_detail_carries_canonical_move():
    out = validate(answer_for(FEN_ROOK), {"move": "Rxe8"})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["correct_move"] == "Rxe8#"
    assert out.detail["correct"] == ["Rxe8#"]


# --- Security ---


def test_client_fen_ignored():
    out = validate(answer_for(FEN_ROOK), {"move": "Rxe8#", "fen": FEN_KNIGHT})
    assert out.result == AttemptResult.CORRECT


def test_client_example_ignored():
    out = validate(answer_for(FEN_ROOK), {"move": "Ra1", "example": "Ra1", "correct_move": "Ra1"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["Rxe8#"]


def test_fake_correctness_metadata_rejected():
    out = validate(answer_for(FEN_ROOK), {"move": "Ra1", "result": "correct"})
    assert out.result == AttemptResult.WRONG


def test_invalid_stored_fen_fails_safe():
    assert validate({"fen": "junk"}, {"move": "Qh7#"}).result == AttemptResult.WRONG


# --- Seed (independent verification) ---


def _independent(fen: str) -> list[str]:
    board = chess.Board(fen)
    mates: list[str] = []
    for move in board.legal_moves:
        san = board.san(move)
        board.push(move)
        try:
            if board.is_checkmate():
                mates.append(san)
        finally:
            board.pop()
    return sorted(mates)


def test_seed_count_idempotent_shapes(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    sides = set()
    for puzzle in puzzles:
        # No position leak: fen column empty, no FEN/SAN in visible payload.
        assert puzzle.fen is None
        assert puzzle.position_json["mode"] == "mate-in-1"
        assert puzzle.position_json["side_to_move"] in ("white", "black")
        assert "fen" not in puzzle.position_json
        assert "example" not in puzzle.position_json
        sides.add(puzzle.position_json["side_to_move"])
        stored = puzzle.answer_json
        expected = _independent(stored["fen"])
        assert len(expected) == 1  # MVP: exactly one mate per puzzle
        assert stored["example"] == expected[0]
        assert stored["mate_count"] == 1
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        # Validator agrees with the independent computation.
        assert validate(stored, {"move": expected[0]}).result == AttemptResult.CORRECT
    assert sides == {"white", "black"}
    assert len({p.initial_rating for p in puzzles}) >= 5


def test_seed_mate_pattern_spread(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    sans = {p.answer_json["example"] for p in puzzles}
    assert any(s.startswith("Q") for s in sans)  # queen mates
    assert any(s.startswith("R") for s in sans)  # rook mates
    assert any(s.startswith("N") for s in sans)  # knight mates
    assert any(s.startswith("B") for s in sans)  # bishop mate
    assert any("x" in s for s in sans)  # capture mates


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


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
        assert entry["position_json"]["side_to_move"] in ("white", "black")
        dumped = res.text
        assert "example" not in dumped


def test_api_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert res.json()["fen"] is None
    assert "answer_json" not in res.json()


def test_api_correct_and_wrong_submit(client, db_session):
    puzzle = _seeded(db_session)
    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"move": puzzle.answer_json["example"]},
            "mode": "practice",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["correct_move"] == puzzle.answer_json["example"]

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "Ra1"}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    malformed = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "zzz"}, "mode": "practice"},
    )
    assert malformed.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"move": "Ra1"}, "mode": "rated"},
    )
    assert rated.status_code == 401
