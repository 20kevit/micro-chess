"""Generation job execution (Phase 07).

A job runs synchronously in a bounded batch (no queues/workers: the
batch cap keeps API latency predictable). Every candidate flows
through the same exercise-aware content validation as manual
content; valid candidates persist as ``validated`` (never
published), invalid candidates are rejected with their reasons
recorded on the job for generator evaluation and debugging.

Reproducibility: the stored seed + generator version + validated
configuration snapshot replay the same candidate sequence. Dedup
against live content may skip already-existing candidates, so a
replay on a non-empty database can accept fewer rows; the pure
candidate sequence itself is deterministic.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

# Exercise content invariants register on import so validation is
# exercise-aware without core flow branching on exercise slugs.
import app.modules.captures.content as _captures_content  # noqa: F401
import app.modules.legal_destinations.content as _legal_content  # noqa: F401
import app.modules.piece_recognition.content as _piece_content  # noqa: F401
from app.modules.generators.models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    TERMINAL_STATUSES,
    GeneratorRun,
)
from app.modules.generators.registry import available_generators, get_generator
from app.modules.puzzles.models import (
    SOURCE_GENERATED,
    STATUS_VALIDATED,
    Puzzle,
    PuzzleStatusHistory,
    PuzzleValidation,
)
from app.modules.puzzles.validation import CONTENT_VALIDATOR_VERSION, validate_puzzle_fields

# Bounded batch: generation must not block normal API requests or
# exhaust storage; larger imports arrive as multiple audited jobs.
MAX_BATCH_SIZE = 50
MIN_BATCH_SIZE = 1
MAX_SEED = 2**31 - 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_run_input(
    *,
    generator_code: str,
    count: int,
    seed: int | None,
    target_rating: float | None,
    difficulty: int | None,
    config: dict,
):
    definition = get_generator(generator_code)
    if definition is None:
        raise ValueError("unknown_generator")
    if not isinstance(count, int) or not MIN_BATCH_SIZE <= count <= MAX_BATCH_SIZE:
        raise ValueError("invalid_count")
    if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= MAX_SEED):
        raise ValueError("invalid_seed")
    if target_rating is not None:
        try:
            numeric = float(target_rating)
        except (TypeError, ValueError):
            raise ValueError("invalid_target_rating")
        if not 100.0 <= numeric <= 3000.0:
            raise ValueError("invalid_target_rating")
    if difficulty is not None and (not isinstance(difficulty, int) or not 1 <= difficulty <= 5):
        raise ValueError("invalid_difficulty")
    if not isinstance(config, dict):
        raise ValueError("invalid_config")
    unknown = sorted(set(config) - set(definition.allowed_config_keys))
    if unknown:
        raise ValueError("unsupported_config")
    return definition


def run_job(
    db: Session,
    *,
    actor_id: int,
    generator_code: str,
    count: int,
    seed: int | None = None,
    target_rating: float | None = None,
    difficulty: int | None = None,
    config: dict[str, Any] | None = None,
) -> GeneratorRun:
    """Create a generation job and execute it synchronously.

    Accepted candidates persist as ``validated`` puzzles with full
    provenance (generator run id, version snapshot on the job,
    configuration snapshot on the job). Nothing is published: review,
    approval, and publication remain explicit human actions.
    """
    config = dict(config or {})
    definition = _validate_run_input(
        generator_code=generator_code,
        count=count,
        seed=seed,
        target_rating=target_rating,
        difficulty=difficulty,
        config=config,
    )
    effective_seed = seed if seed is not None else random.randint(0, MAX_SEED)
    run = GeneratorRun(
        generator_code=definition.code,
        generator_version=definition.version,
        exercise_slug=definition.exercise_slug,
        status=STATUS_RUNNING,
        requested_count=count,
        seed=effective_seed,
        target_rating=float(target_rating) if target_rating is not None else None,
        difficulty=difficulty,
        config_json=config,
        result_json={},
        requested_by_user_id=actor_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    rng = random.Random(effective_seed)
    accepted_ids: list[int] = []
    rejected: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    generated = 0
    try:
        for index in range(count):
            try:
                candidate = definition.build_candidate(rng, config)
            except Exception as exc:
                rejected.append(
                    {"index": index, "reason": "generation_failed", "detail": str(exc)[:200]}
                )
                continue
            generated += 1
            outcome = validate_puzzle_fields(
                db,
                exercise_slug=definition.exercise_slug,
                fen=candidate.get("fen"),
                position_json=candidate.get("position_json"),
                answer_json=candidate.get("answer_json"),
                difficulty=difficulty,
                target_rating=target_rating,
                initial_rating=candidate.get("initial_rating"),
            )
            if outcome.content_hash in seen_hashes:
                rejected.append(
                    {
                        "index": index,
                        "reason": "duplicate_content",
                        "detail": "duplicate of an earlier candidate in this job",
                    }
                )
                continue
            seen_hashes.add(outcome.content_hash)
            if not outcome.ok:
                rejected.append({"index": index, "reason": "validation_failed", "errors": outcome.errors})
                continue
            puzzle = Puzzle(
                exercise_slug=definition.exercise_slug,
                fen=candidate.get("fen"),
                position_json=candidate.get("position_json") or {},
                answer_json=candidate.get("answer_json") or {},
                hint_json=candidate.get("hint_json") or {},
                prompt_fa=(candidate.get("prompt_fa") or "")[:500],
                explanation=(candidate.get("explanation") or "")[:2000],
                initial_rating=float(candidate.get("initial_rating", 1200.0)),
                is_published=False,
                is_archived=False,
                status=STATUS_VALIDATED,
                source=SOURCE_GENERATED,
                generator_run_id=run.id,
                difficulty=difficulty,
                target_rating=float(target_rating) if target_rating is not None else None,
                content_hash=outcome.content_hash,
            )
            db.add(puzzle)
            db.flush()
            db.add(
                PuzzleValidation(
                    puzzle_id=puzzle.id,
                    validator_version=CONTENT_VALIDATOR_VERSION,
                    status="pass",
                    result_json={"generator": definition.code, "errors": []},
                    validated_by_user_id=actor_id,
                )
            )
            db.add(
                PuzzleStatusHistory(
                    puzzle_id=puzzle.id,
                    from_status="draft",
                    to_status=STATUS_VALIDATED,
                    changed_by_user_id=actor_id,
                    reason=f"generated by {definition.code} v{definition.version}",
                )
            )
            accepted_ids.append(puzzle.id)
        run.generated_count = generated
        run.validated_count = len(accepted_ids)
        run.accepted_count = len(accepted_ids)
        run.rejected_count = len(rejected)
        run.result_json = {"accepted_puzzle_ids": accepted_ids, "rejected": rejected}
        run.status = STATUS_COMPLETED
        run.completed_at = _utcnow()
        run.updated_at = _utcnow()
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        # Atomic failure: the loop never commits, so rolling back
        # persists no candidates at all — a failed job never publishes
        # (or even stores) partial content. The failure, configuration,
        # generator version, and timestamps remain traceable on the job.
        db.rollback()
        run = db.get(GeneratorRun, run.id)
        run.generated_count = 0
        run.validated_count = 0
        run.accepted_count = 0
        run.rejected_count = 0
        run.result_json = {
            "accepted_puzzle_ids": [],
            "rejected": [],
            "note": "job aborted before commit; no candidates were persisted",
        }
        run.status = STATUS_FAILED
        run.error = str(exc)[:1000]
        run.completed_at = _utcnow()
        run.updated_at = _utcnow()
        db.commit()
        db.refresh(run)
        return run


def cancel_job(db: Session, *, actor_id: int, run_id: int) -> tuple[GeneratorRun, bool]:
    """Cancel a non-terminal job. Terminal jobs cannot be cancelled."""
    _ = actor_id
    run = db.get(GeneratorRun, run_id)
    if run is None:
        raise ValueError("generator_run_not_found")
    if run.status in TERMINAL_STATUSES:
        raise ValueError("invalid_transition")
    run.status = STATUS_CANCELLED
    run.completed_at = _utcnow()
    run.updated_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run, True


def list_runs(
    db: Session,
    *,
    generator: str | None = None,
    exercise: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[GeneratorRun], int]:
    query = db.query(GeneratorRun)
    if generator:
        query = query.filter(GeneratorRun.generator_code == generator)
    if exercise:
        query = query.filter(GeneratorRun.exercise_slug == exercise)
    if status:
        query = query.filter(GeneratorRun.status == status)
    total = query.count()
    rows = (
        query.order_by(GeneratorRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def generator_view(definition) -> dict[str, Any]:
    return {
        "code": definition.code,
        "exercise_slug": definition.exercise_slug,
        "version": definition.version,
        "description": definition.description,
        "config_schema": definition.config_schema,
        "status": "active",
    }


def run_view(run: GeneratorRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "generator_code": run.generator_code,
        "generator_version": run.generator_version,
        "exercise_slug": run.exercise_slug,
        "status": run.status,
        "requested_count": run.requested_count,
        "generated_count": run.generated_count,
        "validated_count": run.validated_count,
        "accepted_count": run.accepted_count,
        "rejected_count": run.rejected_count,
        "seed": run.seed,
        "target_rating": run.target_rating,
        "difficulty": run.difficulty,
        "config": run.config_json or {},
        "result": run.result_json or {},
        "error": run.error or "",
        "requested_by_user_id": run.requested_by_user_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "completed_at": run.completed_at,
    }


__all__ = [
    "MAX_BATCH_SIZE",
    "available_generators",
    "cancel_job",
    "generator_view",
    "list_runs",
    "run_job",
    "run_view",
]
