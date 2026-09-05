"""Exercise 1 generator: random position/question/answer server-side."""

import random

import chess
import pytest

from app.modules.piece_recognition import generator
from app.modules.piece_recognition.validator import CANONICAL_TARGETS, squares_for_target
from app.modules.puzzles.models import Puzzle

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_canonical_space_is_twelve_color_kind_pairs():
    assert len(CANONICAL_TARGETS) == 12
    pairs = {(t["color"], tuple(t["kinds"])) for t in CANONICAL_TARGETS.values()}
    assert len(pairs) == 12
    for target in CANONICAL_TARGETS.values():
        assert target["color"] in ("white", "black")
        assert len(target["kinds"]) == 1


def test_all_piece_types_covered_both_colors():
    kinds = {tuple(t["kinds"])[0] for t in CANONICAL_TARGETS.values()}
    assert kinds == {"p", "n", "b", "r", "q", "k"}


def test_question_single_target():
    data = generator.question_for_fen("8/8/8/8/3p4/8/PP6/8 w - - 0 1", "black-pawn")
    assert data["squares"] == ["d4"]
    assert data["prompt_fa"]
    assert data["explanation"]


def test_question_multiple_targets():
    data = generator.question_for_fen(STARTPOS, "white-pawn")
    assert data["squares"] == ["a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2"]


def test_question_zero_targets_is_valid():
    data = generator.question_for_fen(STARTPOS, "white-queen")
    # Startpos DOES have a white queen; use a queenless position instead.
    assert data["squares"] == ["d1"]
    queenless = "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12"
    data = generator.question_for_fen(queenless, "white-queen")
    assert data["squares"] == []
    assert data["prompt_fa"]
    # Explanation must teach that selecting nothing is correct.
    assert data["explanation"]


def test_king_targets():
    assert generator.question_for_fen(STARTPOS, "white-king")["squares"] == ["e1"]
    assert generator.question_for_fen(STARTPOS, "black-king")["squares"] == ["e8"]


def test_answers_match_independent_python_chess():
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    for key in CANONICAL_TARGETS:
        target = CANONICAL_TARGETS[key]
        expected = sorted(
            chess.square_name(sq)
            for sq in chess.SQUARES
            for piece in [board.piece_at(sq)]
            if piece is not None
            and piece.symbol().lower() in target["kinds"]
            and (target["color"] == "white") == (piece.color == chess.WHITE)
        )
        assert generator.question_for_fen(fen, key)["squares"] == expected


def test_invalid_fen_and_target_rejected():
    with pytest.raises(ValueError):
        generator.question_for_fen("garbage", "white-pawn")
    with pytest.raises(ValueError):
        generator.question_for_fen(STARTPOS, "nope")


def test_generate_is_random_across_targets():
    rng = random.Random(7)
    keys = {generator.generate_question_data(rng)["target"] for _ in range(60)}
    assert len(keys) >= 6


def test_generate_zero_targets_occur():
    rng = random.Random(1234)
    zero = sum(1 for _ in range(120) if not generator.generate_question_data(rng)["squares"])
    assert zero >= 1


def test_squares_helper_agrees_with_generator():
    rng = random.Random(99)
    for _ in range(20):
        data = generator.generate_question_data(rng)
        assert data["squares"] == squares_for_target(data["fen"], CANONICAL_TARGETS[data["target"]])


def test_create_puzzle_persists_published_row(db_session):
    puzzle = generator.create_puzzle(db_session, random.Random(5))
    assert puzzle.id is not None
    assert puzzle.is_published and not puzzle.is_archived
    assert puzzle.fen and puzzle.prompt_fa and puzzle.explanation
    stored = db_session.get(Puzzle, puzzle.id)
    assert stored.answer_json["squares"] == generator.question_for_fen(
        stored.fen, stored.position_json["target"]
    )["squares"]
