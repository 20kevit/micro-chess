"""Exercise registry: maps exercise slug -> validator (+ optional scorer).

New exercise types plug in here without touching core flow.
Never use a giant if/elif chain; register a validator (and, only when the
exercise needs non-default scoring, a scorer) instead.
"""

from collections.abc import Callable
from typing import Any

from app.modules.rule_engine.base import ValidationResult
from app.modules.scoring_engine.service import score_for

ValidatorFn = Callable[[dict[str, Any], dict[str, Any]], ValidationResult]
ScorerFn = Callable[[ValidationResult], float]

_registry: dict[str, ValidatorFn] = {}
_scorers: dict[str, ScorerFn] = {}


def register_validator(slug: str, fn: ValidatorFn) -> None:
    _registry[slug] = fn


def get_validator(slug: str) -> ValidatorFn | None:
    return _registry.get(slug)


def register_scorer(slug: str, fn: ScorerFn) -> None:
    """Register exercise-specific scoring. Only needed when the default
    result -> score mapping does not apply (e.g. per-square scoring)."""
    _scorers[slug] = fn


def get_scorer(slug: str) -> ScorerFn | None:
    return _scorers.get(slug)


def score_for_answer(slug: str, validation: ValidationResult) -> float:
    """Authoritative score for a validation. Exercise scorer wins when
    registered; otherwise the shared result -> score default applies."""
    fn = get_scorer(slug)
    if fn is not None:
        return fn(validation)
    return score_for(validation.result)


def registered_slugs() -> list[str]:
    return sorted(_registry.keys())


def validate_answer(slug: str, puzzle_answer: dict[str, Any], attempt: dict[str, Any]) -> ValidationResult:
    fn = get_validator(slug)
    if fn is None:
        # Unknown exercise: backend refuses to guess. Frontend must not self-validate.
        from app.modules.rule_engine.base import AttemptResult

        return ValidationResult(result=AttemptResult.WRONG, message_key="unknown_exercise")
    return fn(puzzle_answer, attempt)
