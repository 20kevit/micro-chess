"""Exercise registry: maps exercise slug -> validator.

New exercise types plug in here without touching core flow.
Never use a giant if/elif chain; register a validator instead.
"""

from collections.abc import Callable
from typing import Any

from app.modules.rule_engine.base import ValidationResult

ValidatorFn = Callable[[dict[str, Any], dict[str, Any]], ValidationResult]

_registry: dict[str, ValidatorFn] = {}


def register_validator(slug: str, fn: ValidatorFn) -> None:
    _registry[slug] = fn


def get_validator(slug: str) -> ValidatorFn | None:
    return _registry.get(slug)


def registered_slugs() -> list[str]:
    return sorted(_registry.keys())


def validate_answer(slug: str, puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fn = get_validator(slug)
    if fn is None:
        # Unknown exercise: backend refuses to guess. Frontend must not self-validate.
        from app.modules.rule_engine.base import AttemptResult

        return ValidationResult(result=AttemptResult.WRONG, message_key="unknown_exercise")
    return fn(puzzle_answer, attempt)
