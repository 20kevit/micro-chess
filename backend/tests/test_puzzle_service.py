"""Puzzle answer immutability + attempt flow (practice never rates)."""

import pytest

from app.modules.exercises import models as ex_models
from app.modules.exercises import registry
from app.modules.progress import service as attempt_service
from app.modules.puzzles import service as puzzle_service
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptMode, AttemptResult, ValidationResult


@pytest.fixture()
def seeded(db_session):
    db_session.add(
        ex_models.Exercise(slug="demo-ex", title_fa="دمو", title_en="demo", sort_order=0)
    )
    db_session.commit()

    registry.register_validator(
        "demo-ex",
        lambda expected, given: ValidationResult(
            result=AttemptResult.CORRECT if given == expected else AttemptResult.WRONG,
            message_key="feedback.correct",
        ),
    )
    try:
        puzzle = puzzle_service.create_draft(
            db_session,
            exercise_slug="demo-ex",
            fen=None,
            position_json={},
            answer_json={"square": "e4"},
            hint_json={},
        )
        puzzle_service.publish(db_session, puzzle)
        yield puzzle
    finally:
        registry._registry.pop("demo-ex", None)


def test_answer_immutable_after_publish(db_session, seeded):
    with pytest.raises(Exception):
        puzzle_service.update_answer(db_session, seeded, {"square": "d5"})


def test_practice_attempt_scores_without_rating(db_session, seeded):
    attempt, _key, _detail = attempt_service.submit_attempt(
        db_session,
        user_id=1,
        puzzle_id=seeded.id,
        answer={"square": "e4"},
        mode=AttemptMode.PRACTICE,
    )
    assert attempt.result == AttemptResult.CORRECT.value
    assert attempt.score == 1.0
    assert attempt.rating_delta is None
    assert attempt.answer_json == {"square": "e4"}


def test_archived_puzzle_rejects_attempts(db_session, seeded):
    puzzle_service.archive(db_session, seeded)
    with pytest.raises(ValueError):
        attempt_service.submit_attempt(
            db_session,
            user_id=None,
            puzzle_id=seeded.id,
            answer={"square": "e4"},
            mode=AttemptMode.PRACTICE,
        )


def test_client_timeout_result(db_session, seeded):
    attempt, _key, _detail = attempt_service.submit_attempt(
        db_session,
        user_id=1,
        puzzle_id=seeded.id,
        answer={},
        mode=AttemptMode.PRACTICE,
        client_result="timeout",
    )
    assert attempt.result == AttemptResult.TIMEOUT.value
    assert attempt.score == 0.0
