"""Exercise 1 generator: random position/question/answer server-side."""

import random
import sqlite3

import chess
import pytest

from app.modules.piece_recognition import generator
from app.modules.piece_recognition.categories import (
    CATEGORIES,
    CATEGORY_KEYS,
    GROUP_KEYS,
)
from app.modules.piece_recognition.validator import CANONICAL_TARGETS, squares_for_target
from app.modules.positions import repository as positions_repo
from app.modules.puzzles.models import Puzzle

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture(autouse=True)
def small_source_db(tmp_path, monkeypatch):
    """Pin a tiny puzzles.db so tests exercise the real read path fast
    instead of scanning a multi-GB Lichess dump if one is present."""
    path = tmp_path / "puzzles.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        'CREATE TABLE "puzzles" ("PuzzleId" TEXT, "FEN" TEXT, "Rating" INTEGER, "Themes" TEXT, "Moves" TEXT)'
    )
    for i, fen in enumerate(positions_repo.FALLBACK_FENS):
        conn.execute(
            "INSERT INTO puzzles (PuzzleId, FEN, Rating, Themes, Moves) VALUES (?, ?, ?, ?, ?)",
            (f"p{i}", fen, 1500, "t", "e2e4"),
        )
    conn.commit()
    conn.close()
    monkeypatch.setenv(positions_repo.SOURCE_ENV_VAR, str(path))
    return path


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


def test_sixteen_categories_twelve_individual_four_groups():
    assert len(CATEGORIES) == 16
    assert len(GROUP_KEYS) == 4
    for key in GROUP_KEYS:
        assert CATEGORIES[key].color in ("white", "black")
        assert len(CATEGORIES[key].kinds) == 2
    assert CATEGORIES["white-minor"].kinds == ("n", "b")
    assert CATEGORIES["black-heavy"].kinds == ("r", "q")


def test_group_minor_squares_and_prompt():
    data = generator.question_for_fen(STARTPOS, "white-minor")
    assert data["squares"] == ["b1", "c1", "f1", "g1"]
    assert data["prompt_fa"] == "تمام سوارهای سبک سفید را پیدا کن."


def test_group_heavy_squares_and_prompt():
    data = generator.question_for_fen(STARTPOS, "black-heavy")
    assert data["squares"] == ["a8", "d8", "h8"]
    assert data["prompt_fa"] == "تمام سوارهای سنگین سیاه را پیدا کن."


def test_group_zero_targets_valid():
    pawns_only = "8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1"
    data = generator.question_for_fen(pawns_only, "black-minor")
    assert data["squares"] == []
    assert data["prompt_fa"] == "تمام سوارهای سبک سیاه را پیدا کن."
    assert data["explanation"]


def test_group_answers_match_python_chess():
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    for key in GROUP_KEYS:
        cat = CATEGORIES[key]
        expected = sorted(
            chess.square_name(sq)
            for sq in chess.SQUARES
            for piece in [board.piece_at(sq)]
            if piece is not None
            and piece.symbol().lower() in cat.kinds
            and (cat.color == "white") == (piece.color == chess.WHITE)
        )
        assert generator.question_for_fen(fen, key)["squares"] == expected


def test_groups_appear_regularly_without_dominating():
    rng = random.Random(20260601)
    keys = [generator.generate_question_data(rng)["target"] for _ in range(400)]
    assert set(keys) == set(CATEGORY_KEYS)
    group_hits = sum(1 for k in keys if k in GROUP_KEYS)
    assert group_hits >= 40  # uniform would give ~100; generous lower bound


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
        assert data["squares"] == squares_for_target(
            data["fen"], CATEGORIES[data["target"]].target_spec()
        )


def test_create_puzzle_persists_published_row(db_session):
    puzzle = generator.create_puzzle(db_session, random.Random(5))
    assert puzzle.id is not None
    assert puzzle.is_published and not puzzle.is_archived
    assert puzzle.fen and puzzle.prompt_fa and puzzle.explanation
    stored = db_session.get(Puzzle, puzzle.id)
    assert stored.answer_json["squares"] == generator.question_for_fen(
        stored.fen, stored.position_json["target"]
    )["squares"]


def test_identical_rows_reused_not_duplicated(db_session, monkeypatch):
    first = generator.create_puzzle(db_session, random.Random(11))
    before = db_session.query(Puzzle).count()
    match, identical = generator._match_existing(
        db_session, first.fen, first.position_json["target"], set()
    )
    assert identical and match is not None and match.id == first.id
    # Pin the generator to the identical combo: no new row is created.
    full = generator.question_for_fen(first.fen, first.position_json["target"])
    monkeypatch.setattr(generator, "generate_question_data", lambda *a, **k: dict(full))
    again = generator.create_puzzle(db_session)
    assert again.id == first.id
    assert db_session.query(Puzzle).count() == before
    # ...unless that row is excluded, in which case a fresh row appears.
    fresh = generator.create_puzzle(db_session, exclude_ids={first.id})
    assert fresh.id != first.id
    assert db_session.query(Puzzle).count() == before + 1


def test_exclude_ids_steer_away_from_shown(db_session):
    first = generator.create_puzzle(db_session, random.Random(3))
    other = generator.create_puzzle(db_session, random.Random(3), exclude_ids={first.id})
    # Best-effort: either a different row or (tiny pool exhausted) the same.
    assert other.id is not None
    if other.id == first.id:
        match, _ = generator._match_existing(
            db_session, first.fen, first.position_json["target"], {first.id}
        )
        assert match is None  # only identical row is the excluded one
