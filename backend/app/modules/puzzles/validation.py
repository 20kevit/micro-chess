"""Phase 07 content validation: server-authoritative puzzle checks.

Validation is exercise-aware without branching core flow on exercise
slugs: generic structural/chess/metadata checks always run, and
exercise-specific structural checks plug in via
``register_content_validator`` (same pattern as the answer registry).

A failed validation blocks progression to the next lifecycle stage;
results are persisted as ``PuzzleValidation`` rows by the admin
service so every transition stays auditable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

CONTENT_VALIDATOR_VERSION = "1"

# Rating bounds shared with the rating engine clamp [100, 3000].
MIN_RATING = 100.0
MAX_RATING = 3000.0
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

ContentValidatorFn = Callable[[dict[str, Any]], list[dict[str, Any]]]

_content_validators: dict[str, ContentValidatorFn] = {}


def register_content_validator(slug: str, fn: ContentValidatorFn) -> None:
    """Register an exercise-specific structural check.

    ``fn`` receives the candidate fields dict
    (exercise_slug/fen/position_json/answer_json/...) and returns a list
    of error dicts (empty when the exercise-specific invariants hold).
    """
    _content_validators[slug] = fn


def get_content_validator(slug: str) -> ContentValidatorFn | None:
    return _content_validators.get(slug)


def registered_content_slugs() -> list[str]:
    return sorted(_content_validators)


def content_hash_for(exercise_slug: str, fen: str | None, answer_json: dict) -> str:
    """Stable dedup hash over canonical (exercise, fen, answer) content."""
    canonical = json.dumps(
        {"exercise_slug": exercise_slug, "fen": fen or "", "answer_json": answer_json or {}},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ContentValidationOutcome:
    ok: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    content_hash: str = ""


def _known_exercise(db, slug: str) -> bool:
    from app.modules.exercises import registry
    from app.modules.exercises.models import Exercise

    if db.get(Exercise, slug) is not None:
        return True
    return slug in registry.registered_slugs()


def validate_puzzle_fields(
    db,
    *,
    exercise_slug: str,
    fen: str | None,
    position_json: dict | None,
    answer_json: dict | None,
    difficulty: int | None = None,
    target_rating: float | None = None,
    initial_rating: float | None = None,
    prompt_fa: str = "",
    explanation: str = "",
    exclude_puzzle_id: int | None = None,
    strict_contract: bool = False,
) -> ContentValidationOutcome:
    """Run all Phase 07 content checks. Never mutates the database."""
    from app.modules.puzzles.models import Puzzle

    errors: list[dict[str, Any]] = []
    slug = (exercise_slug or "").strip()
    position = position_json if isinstance(position_json, dict) else {}
    answer = answer_json if isinstance(answer_json, dict) else {}

    # 1. Exercise compatibility.
    if not slug or not _known_exercise(db, slug):
        errors.append({"code": "unknown_exercise", "detail": "exercise is not registered"})

    # 2. Required answer structure.
    if not isinstance(answer_json, dict) or not answer:
        errors.append({"code": "answer_missing", "detail": "answer_json must be a non-empty object"})
    elif len(json.dumps(answer, sort_keys=True, ensure_ascii=False)) > 8000:
        errors.append({"code": "answer_too_large", "detail": "answer payload exceeds the size bound"})

    contract = None
    if strict_contract and slug:
        from app.modules.exercises.answer_contracts import answer_contract_for, validate_contract_shape

        contract = answer_contract_for(slug)
        if contract is not None and isinstance(answer, dict) and answer:
            errors.extend(
                validate_contract_shape(
                    contract,
                    answer=answer,
                    position=position,
                    fen=fen,
                )
            )

    # 3. Chess legality of the position representation.
    if fen:
        try:
            from app.modules.chess_engine.board import parse_board

            parse_board(fen)
        except Exception:
            errors.append({"code": "invalid_fen", "detail": "fen is not a valid chess position"})

    # 4. Declared metadata bounds (generation targets, not guarantees).
    if difficulty is not None and (not isinstance(difficulty, int) or not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY):
        errors.append({"code": "invalid_difficulty", "detail": "difficulty must be an integer 1-5"})
    for label, value in (("target_rating", target_rating), ("initial_rating", initial_rating)):
        if value is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                errors.append({"code": f"invalid_{label}", "detail": f"{label} must be numeric"})
                continue
            if not MIN_RATING <= numeric <= MAX_RATING:
                errors.append({"code": f"invalid_{label}", "detail": f"{label} must be within 100-3000"})

    # 5. Answer-leakage guard: player-visible position must never duplicate
    # the definitive answer object verbatim.
    if position and answer and position == answer:
        errors.append(
            {"code": "answer_leakage", "detail": "position_json must not duplicate answer_json"}
        )

    if contract is not None and not any(
        str(error.get("code", "")).startswith("answer_field_") for error in errors
    ):
        from app.modules.exercises.answer_contracts import canonical_attempt
        from app.modules.exercises.registry import validate_answer
        from app.modules.rule_engine.base import AttemptResult

        attempt = canonical_attempt(contract, answer)
        if attempt is not None:
            result = validate_answer(slug, answer, attempt)
            if result.result != AttemptResult.CORRECT:
                errors.append(
                    {
                        "code": "answer_validator_rejected",
                        "detail": "stored answer is not accepted by its exercise validator",
                    }
                )

    # 6. Exercise-specific structural invariants (pluggable, no slug chain).
    hook = get_content_validator(slug) if slug else None
    if hook is not None and answer:
        try:
            hook_errors = hook(
                {
                    "exercise_slug": slug,
                    "fen": fen,
                    "position_json": position,
                    "answer_json": answer,
                    "prompt_fa": prompt_fa or "",
                    "explanation": explanation or "",
                }
            )
        except Exception:
            hook_errors = [{"code": "exercise_check_failed", "detail": "exercise invariant check failed"}]
        errors.extend(hook_errors or [])

    # 7. Deduplication against gated (non-draft, non-retired) content.
    # Drafts are work-in-progress and excluded: when two identical
    # drafts exist, the first one to validate wins and the second is
    # then rejected as a duplicate.
    content_hash = content_hash_for(slug, fen, answer)
    if answer and slug:
        dup_query = db.query(Puzzle).filter(
            Puzzle.content_hash == content_hash,
            Puzzle.is_archived == False,  # noqa: E712
            Puzzle.status.in_(["validated", "reviewed", "approved", "published"]),
        )
        if exclude_puzzle_id is not None:
            dup_query = dup_query.filter(Puzzle.id != exclude_puzzle_id)
        duplicate = dup_query.order_by(Puzzle.id).first()
        if duplicate is not None:
            errors.append(
                {
                    "code": "duplicate_content",
                    "detail": "materially equivalent puzzle already exists",
                    "duplicate_of": duplicate.id,
                }
            )

    return ContentValidationOutcome(ok=not errors, errors=errors, content_hash=content_hash)
