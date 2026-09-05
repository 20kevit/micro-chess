"""Piece Recognition per-square scoring (Production v1).

score = 5*correct - 1*missed - 2*wrong, backend-authoritative, never
clamped, independent of the CORRECT/PARTIAL/WRONG label.
"""

from app.modules.exercises import registry
from app.modules.piece_recognition.scoring import (
    CORRECT_POINTS,
    MISSED_COST,
    WRONG_COST,
    score_squares,
)
from app.modules.piece_recognition.validator import SLUG, validate
from app.modules.rule_engine.base import AttemptResult, ValidationResult
from app.modules.scoring_engine.service import score_for


def _score(puzzle_squares, selected):
    return registry.score_for_answer(
        SLUG, validate({"squares": puzzle_squares}, {"selected_squares": selected})
    )


def test_spec_example_scores_seven():
    assert _score(["e4", "g7", "b2"], ["e4", "g7", "d5"]) == 7.0


def test_spec_scoring_examples():
    cases = [
        ([], [], AttemptResult.CORRECT, 5.0),
        ([], ["e4"], AttemptResult.WRONG, -2.0),
        (["e4"], ["e4"], AttemptResult.CORRECT, 5.0),
        (["e4"], [], AttemptResult.WRONG, -1.0),
        (["e4", "e5"], ["e4"], AttemptResult.PARTIAL, 4.0),
        (["e4", "e5"], ["e4", "e6"], AttemptResult.PARTIAL, 2.0),
    ]
    for target, selected, expected_result, expected_score in cases:
        out = validate({"squares": target}, {"selected_squares": selected})
        assert out.result == expected_result, (target, selected)
        assert registry.score_for_answer(SLUG, out) == expected_score, (target, selected)


def test_combination_negative_three():
    # correct=1, missed=2, wrong=3 -> 5 - 2 - 6 = -3
    out = validate({"squares": ["a1", "b2", "c3"]}, {"selected_squares": ["a1", "e4", "e5", "e6"]})
    assert out.detail == {
        "correct": ["a1"],
        "missed": ["b2", "c3"],
        "wrong": ["e4", "e5", "e6"],
    }
    assert registry.score_for_answer(SLUG, out) == -3.0


def test_zero_target_correct_awards_plus_five():
    out = validate({"squares": []}, {"selected_squares": []})
    assert out.result == AttemptResult.CORRECT
    assert registry.score_for_answer(SLUG, out) == 5.0


def test_zero_target_wrong_costs_two_per_square():
    out = validate({"squares": []}, {"selected_squares": ["e4"]})
    assert out.result == AttemptResult.WRONG
    assert registry.score_for_answer(SLUG, out) == -2.0
    out2 = validate({"squares": []}, {"selected_squares": ["e4", "d5"]})
    assert registry.score_for_answer(SLUG, out2) == -4.0


def test_negative_scores_not_clamped():
    assert _score(["a1"], ["z9"]) == -3.0  # missed 1 (-1) + malformed wrong (-2)


def test_score_independent_of_label():
    # Same label, different scores; same score impossible across labels here,
    # but the point stands: label comes from the validator, points from detail.
    partial = validate({"squares": ["a1", "a2"]}, {"selected_squares": ["a1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert registry.score_for_answer(SLUG, partial) == 4.0
    wrong = validate({"squares": ["a1", "a2"]}, {"selected_squares": ["h8"]})
    assert wrong.result == AttemptResult.WRONG
    assert registry.score_for_answer(SLUG, wrong) == -4.0


def test_constants_match_spec():
    assert (CORRECT_POINTS, MISSED_COST, WRONG_COST) == (5, 1, 2)


def test_scorer_registered_and_default_untouched():
    assert registry.get_scorer(SLUG) is score_squares
    assert registry.get_scorer("no-such-exercise") is None
    assert score_for(AttemptResult.CORRECT) == 1.0
    assert score_for(AttemptResult.PARTIAL) == 0.5
    assert score_for(AttemptResult.WRONG) == 0.0
    assert registry.score_for_answer(
        "no-such-exercise", ValidationResult(result=AttemptResult.CORRECT)
    ) == 1.0


def test_scorer_defensive_on_malformed_detail():
    assert score_squares(ValidationResult(result=AttemptResult.WRONG, detail={})) == 0.0
    assert (
        score_squares(ValidationResult(result=AttemptResult.WRONG, detail=None)) == 0.0
    )
