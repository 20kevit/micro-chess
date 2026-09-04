"""Registry routes validators per exercise slug (no if/elif chain)."""

from app.modules.exercises import registry
from app.modules.rule_engine.base import AttemptResult, ValidationResult


def test_unknown_slug_returns_wrong():
    out = registry.validate_answer("nope", {}, {})
    assert out.result == AttemptResult.WRONG
    assert out.message_key == "unknown_exercise"


def test_register_and_dispatch():
    def fake_validator(puzzle_answer, attempt):
        assert puzzle_answer == {"a": 1}
        assert attempt == {"a": 1}
        return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct")

    registry.register_validator("test-ex", fake_validator)
    try:
        out = registry.validate_answer("test-ex", {"a": 1}, {"a": 1})
        assert out.result == AttemptResult.CORRECT
    finally:
        registry._registry.pop("test-ex", None)
