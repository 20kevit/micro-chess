"""Piece Recognition validation rules + seed correctness."""

import chess

from app.modules.piece_recognition import seed as seed_mod
from app.modules.piece_recognition.validator import CANONICAL_TARGETS, SLUG, TARGETS, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult

ANSWER = {"squares": ["a2", "c4", "f7"]}


def test_correct_result():
    out = validate(ANSWER, {"selected_squares": ["a2", "c4", "f7"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["a2", "c4", "f7"], "missed": [], "wrong": []}


def test_partial_missed_only():
    out = validate(ANSWER, {"selected_squares": ["a2", "c4"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["a2", "c4"]
    assert out.detail["missed"] == ["f7"]
    assert out.detail["wrong"] == []


def test_partial_wrong_only():
    out = validate(ANSWER, {"selected_squares": ["a2", "c4", "f7", "e5"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["wrong"] == ["e5"]


def test_partial_missed_and_wrong():
    out = validate(ANSWER, {"selected_squares": ["a2", "e5"]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail == {"correct": ["a2"], "missed": ["c4", "f7"], "wrong": ["e5"]}


def test_wrong_no_overlap():
    out = validate(ANSWER, {"selected_squares": ["e5", "h1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["correct"] == []


def test_empty_answer_is_wrong():
    assert validate(ANSWER, {"selected_squares": []}).result == AttemptResult.WRONG
    assert validate(ANSWER, {}).result == AttemptResult.WRONG


def test_zero_target_empty_selection_is_correct():
    # Practice must not terminate on zero targets: submitting nothing is CORRECT.
    out = validate({"squares": []}, {"selected_squares": []})
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": [], "missed": [], "wrong": []}


def test_zero_target_any_selection_is_wrong():
    assert validate({"squares": []}, {"selected_squares": ["e4"]}).result == AttemptResult.WRONG


def test_missing_target_is_not_correct():
    assert validate({"squares": ["e4"]}, {"selected_squares": []}).result == AttemptResult.WRONG
    assert validate({"squares": ["e4"]}, {"selected_squares": ["d5"]}).result == AttemptResult.WRONG


def test_extra_square_is_not_correct():
    assert validate({"squares": ["e4"]}, {"selected_squares": ["e4", "d5"]}).result == AttemptResult.PARTIAL


def test_canonical_targets_cover_all_kinds_both_colors():
    assert len(CANONICAL_TARGETS) == 12
    assert "white-king" in CANONICAL_TARGETS and "black-king" in CANONICAL_TARGETS


def test_malformed_squares_count_as_wrong():
    out = validate({"squares": ["a2"]}, {"selected_squares": ["a2", "z9", "e", 42, None]})
    assert out.result == AttemptResult.PARTIAL
    assert out.detail["correct"] == ["a2"]
    assert len(out.detail["wrong"]) == 4


def test_malformed_only_is_wrong():
    out = validate({"squares": ["a2"]}, {"selected_squares": ["zzz"]})
    assert out.result == AttemptResult.WRONG


def test_duplicates_and_case_normalized():
    out = validate(ANSWER, {"selected_squares": ["A2", "a2", "C4", "F7"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["wrong"] == []


def test_registered_in_registry():
    from app.modules.exercises import registry

    assert registry.get_validator(SLUG) is not None


def _independent_squares(fen: str, target_key: str) -> list[str]:
    """Recompute expected squares directly with python-chess (not the helper)."""
    target = TARGETS[target_key]
    board = chess.Board(fen)  # raises on invalid FEN
    found = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.symbol().lower() not in target["kinds"]:
            continue
        if target["color"] == "white" and piece.color != chess.WHITE:
            continue
        if target["color"] == "black" and piece.color != chess.BLACK:
            continue
        found.append(chess.square_name(sq))
    return sorted(found)


def test_seed_count_and_variety(db_session):
    assert seed_mod.seed_db(db_session) == 15
    # Idempotent: second run creates nothing.
    assert seed_mod.seed_db(db_session) == 0
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    ratings = {p.initial_rating for p in puzzles}
    targets = {p.position_json.get("target") for p in puzzles}
    assert len(ratings) >= 5
    assert len(targets) >= 6
    assert all(
        p.prompt_fa
        and p.explanation
        and not p.is_published
        and p.status == "validated"
        for p in puzzles
    )


def test_seed_answers_match_fen(db_session):
    seed_mod.seed_db(db_session)
    puzzles = (
        db_session.query(Puzzle)
        .filter(Puzzle.exercise_slug == SLUG)
        .order_by(Puzzle.id)
        .all()
    )
    assert puzzles
    for puzzle in puzzles:
        assert puzzle.fen
        expected = _independent_squares(puzzle.fen, puzzle.position_json["target"])
        assert expected, f"puzzle {puzzle.id} has empty answer"
        assert puzzle.answer_json["squares"] == expected
