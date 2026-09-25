"""Phase 12 content-management operations (Exercise & Content Management).

Read-only aggregates and lifecycle-safe mutations that power the admin
Exercise Workspace, Puzzle Library, review workflow, and content-health
views. Business rules live here; routers stay thin.

Reused, never duplicated:

* lifecycle + audit + supply stats: ``app.modules.admin.service``
* content validation: ``app.modules.puzzles.validation``
* answer semantics: exercise validators via
  ``app.modules.exercises.answer_contracts``
* generators: ``app.modules.generators``
* learning signals: ``evidence`` / ``skill_state`` taxonomy + ``progress``
* recommendations: ``adaptive`` rows (read-only)

No new persistence, no fabricated metrics, no per-slug branching.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.admin import service as admin_service
from app.modules.evidence import taxonomy as evidence_taxonomy
from app.modules.exercises import answer_contracts, registry
from app.modules.exercises.models import Exercise
from app.modules.generators import service as generator_service
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import (
    STATUS_APPROVED,
    STATUS_PUBLISHED,
    STATUS_REVIEWED,
    STATUS_VALIDATED,
    Puzzle,
    PuzzleValidation,
)
from app.modules.puzzles.validation import validate_puzzle_fields


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- answer contracts --------------------------------------------------------


def answer_contract(db: Session, slug: str) -> dict | None:
    """Typed answer contract for an exercise plus authoring support flags.

    Returns None for unknown slugs. ``validator_registered`` tells the
    admin whether server-side validation exists; ``generator_available``
    whether automatic generation is offered for the exercise.
    """
    contract = answer_contracts.answer_contract_for(slug)
    if contract is None:
        if db.get(Exercise, slug) is None and slug not in registry.registered_slugs():
            return None
        contract = {
            "exercise_slug": slug,
            "answer_type": "structured",
            "answer_fields": [],
            "attempt_field": "",
            "fen_derived": False,
            "needs_board": True,
            "position_fields": [],
            "notes": "",
        }
    generator_codes = [
        definition.code
        for definition in generator_service.available_generators()
        if definition.exercise_slug == slug
    ]
    return {
        **contract,
        "validator_registered": slug in registry.registered_slugs(),
        "generator_available": bool(generator_codes),
        "generator_codes": generator_codes,
    }


def exercise_generators(slug: str) -> list[dict]:
    """Generator definitions targeting one exercise (admin-triggered only)."""
    return [
        generator_service.generator_view(definition)
        for definition in generator_service.available_generators()
        if definition.exercise_slug == slug
    ]


# --- exercise creation -------------------------------------------------------


def create_exercise(db: Session, *, actor_id: int, fields: dict) -> Exercise:
    """Create a catalog exercise. The slug must resolve to a registered
    validator: a database-only exercise without server-side rules would
    be fake content support, so creation is refused instead."""
    slug = (fields.get("slug") or "").strip()
    if not slug or len(slug) > 100:
        raise ValueError("invalid_slug")
    if db.get(Exercise, slug) is not None:
        raise ValueError("exercise_exists")
    if slug not in registry.registered_slugs():
        raise ValueError("exercise_not_implemented")
    title_fa = (fields.get("title_fa") or "").strip()
    if not title_fa:
        raise ValueError("invalid_title")
    exercise = Exercise(
        slug=slug,
        title_fa=title_fa[:200],
        title_en=(fields.get("title_en") or "").strip()[:200],
        description=(fields.get("description") or "").strip()[:1000],
        is_active=bool(fields.get("is_active", True)),
        sort_order=fields.get("sort_order", 0),
    )
    if not isinstance(exercise.sort_order, int) or exercise.sort_order < 0:
        raise ValueError("invalid_sort_order")
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    admin_service.record_audit(
        db,
        actor_id=actor_id,
        action="exercises.create",
        target_type="exercise",
        target_id=exercise.slug,
        metadata={"title_fa": exercise.title_fa},
    )
    return exercise


# --- preview validation (no writes) ------------------------------------------


def preview_validate(db: Session, *, fields: dict) -> dict:
    """Authoritative validation of candidate content without persisting.

    Powers the editor "Validate" button: position + answer are checked
    through the same exercise-aware gates as publish, including the
    exercise validator's correctness check where the contract is
    FEN-derived. Never mutates the database.
    """
    slug = (fields.get("exercise_slug") or "").strip()
    outcome = validate_puzzle_fields(
        db,
        exercise_slug=slug,
        fen=fields.get("fen"),
        position_json=fields.get("position_json") or {},
        answer_json=fields.get("answer_json") or {},
        difficulty=fields.get("difficulty"),
        target_rating=fields.get("target_rating"),
        initial_rating=fields.get("initial_rating", 1200.0),
        prompt_fa=fields.get("prompt_fa") or "",
        explanation=fields.get("explanation") or "",
        exclude_puzzle_id=fields.get("exclude_puzzle_id"),
        strict_contract=True,
    )
    errors = list(outcome.errors)
    # FEN-derived contracts: also verify the stored answer is actually
    # correct per the exercise validator (authoring-time answer check).
    contract = answer_contracts.answer_contract_for(slug)
    if contract and contract["fen_derived"] and outcome.ok:
        check = _check_derived_answer(slug, fields.get("answer_json") or {})
        if check is not None:
            errors.append(check)
    return {"ok": not errors, "errors": errors, "content_hash": outcome.content_hash}


def _check_derived_answer(slug: str, answer_json: dict) -> dict | None:
    """Verify a FEN-derived answer solves its own position.

    Replays the canonical attempt through the exercise's registered
    validator: e.g. a pin triplet must validate CORRECT against its FEN,
    a checkmate FEN must classify cleanly. Returns an error dict when
    the authored answer does not hold, else None.
    """
    validator = registry.get_validator(slug)
    if validator is None:
        return None
    try:
        if slug == "pin":
            from app.modules.rule_engine.base import AttemptResult

            result = validator(answer_json, {"squares": list(answer_json.get("pin") or [])})
            if result.result != AttemptResult.CORRECT:
                return {
                    "code": "answer_not_solving",
                    "detail": "pin triplet does not match the position",
                }
        elif slug == "is-checkmate":
            from app.modules.checkmate.validator import classify

            classify(answer_json.get("fen") or "")
        elif slug == "get-out-of-check":
            from app.modules.get_out_of_check.validator import escaping_moves

            moves = escaping_moves(answer_json.get("fen") or "")
            if not moves:
                return {"code": "answer_not_solving", "detail": "no escaping move exists"}
        elif slug == "chinese-board":
            from app.modules.chinese_board import pieces as chinese_pieces

            chinese_pieces.extract_pieces(answer_json.get("fen") or "")
    except Exception:
        return {"code": "answer_not_solving", "detail": "answer does not solve the position"}
    return None


# --- bulk operations ---------------------------------------------------------


BULK_ACTIONS = (
    "validate",
    "approve_review",  # validated -> reviewed (approve decision)
    "approve",  # reviewed -> approved
    "publish",
    "quarantine",
    "release",
    "reject",
    "retire",
    "restore",
)

# Capability each bulk action requires (mirrors the single-item routes:
# quarantine/reject/release reuse PUZZLES_RETIRE, restore PUZZLES_PUBLISH).
BULK_CAPABILITIES = {
    "validate": "puzzles.validate",
    "approve_review": "puzzles.review",
    "approve": "puzzles.approve",
    "publish": "puzzles.publish",
    "quarantine": "puzzles.retire",
    "release": "puzzles.retire",
    "reject": "puzzles.retire",
    "retire": "puzzles.retire",
    "restore": "puzzles.publish",
}

MAX_BULK_SIZE = 50


def bulk_puzzle_action(
    db: Session, *, actor_id: int, puzzle_ids: list[int], action: str, reason: str = ""
) -> dict:
    """Apply one lifecycle action to many puzzles. Each item passes the
    same gates as the single-item path; failures are per-item and never
    abort the batch. Destructive actions require an explicit reason."""
    if action not in BULK_ACTIONS:
        raise ValueError("invalid_action")
    if not isinstance(puzzle_ids, list) or not puzzle_ids:
        raise ValueError("invalid_ids")
    if len(puzzle_ids) > MAX_BULK_SIZE:
        raise ValueError("bulk_too_large")
    if action in ("quarantine", "reject", "retire") and not (reason or "").strip():
        raise ValueError("reason_required")

    succeeded: list[int] = []
    failed: list[dict] = []
    for puzzle_id in puzzle_ids:
        try:
            puzzle_id = int(puzzle_id)
        except (TypeError, ValueError):
            failed.append({"id": puzzle_id, "error": "invalid_id"})
            continue
        try:
            if action == "validate":
                admin_service.validate_puzzle(db, actor_id=actor_id, puzzle_id=puzzle_id)
            elif action == "approve_review":
                admin_service.review_puzzle(
                    db, actor_id=actor_id, puzzle_id=puzzle_id,
                    decision="approve", notes=(reason or "")[:2000],
                )
            elif action == "approve":
                admin_service.approve_puzzle(db, actor_id=actor_id, puzzle_id=puzzle_id)
            elif action == "publish":
                admin_service.publish_puzzle(db, actor_id=actor_id, puzzle_id=puzzle_id)
            elif action == "quarantine":
                admin_service.quarantine_puzzle(
                    db, actor_id=actor_id, puzzle_id=puzzle_id, reason=reason)
            elif action == "release":
                admin_service.release_puzzle(
                    db, actor_id=actor_id, puzzle_id=puzzle_id, reason=reason)
            elif action == "reject":
                admin_service.reject_puzzle(
                    db, actor_id=actor_id, puzzle_id=puzzle_id, reason=reason)
            elif action == "retire":
                admin_service.retire_puzzle(db, actor_id=actor_id, puzzle_id=puzzle_id)
            elif action == "restore":
                admin_service.restore_puzzle(
                    db, actor_id=actor_id, puzzle_id=puzzle_id, reason=reason)
            succeeded.append(puzzle_id)
        except ValueError as exc:
            db.rollback()
            failed.append({"id": puzzle_id, "error": str(exc)})
        except Exception:
            db.rollback()
            failed.append({"id": puzzle_id, "error": "internal_error"})
    admin_service.record_audit(
        db,
        actor_id=actor_id,
        action=f"puzzles.bulk_{action}",
        target_type="puzzle",
        target_id=f"{len(succeeded)}_succeeded_{len(failed)}_failed",
        metadata={"action": action, "succeeded": len(succeeded), "failed": len(failed)},
        result="ok" if not failed else "partial",
    )
    return {"action": action, "succeeded": succeeded, "failed": failed}


# --- per-puzzle usage ----------------------------------------------------------


def puzzle_usage(db: Session, puzzle_id: int, *, limit: int = 20) -> dict:
    """Real usage aggregates for one puzzle (attempts, results, timing)."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    rows = (
        db.query(Attempt.result, func.count(Attempt.id))
        .filter(Attempt.puzzle_id == puzzle_id)
        .group_by(Attempt.result)
        .all()
    )
    by_result = {result: int(count) for result, count in rows}
    attempts = sum(by_result.values())
    avg_ms = (
        db.query(func.avg(Attempt.duration_ms))
        .filter(Attempt.puzzle_id == puzzle_id, Attempt.duration_ms.isnot(None))
        .scalar()
    )
    return {
        "puzzle_id": puzzle_id,
        "attempts": attempts,
        "by_result": by_result,
        "success_rate": (by_result.get("correct", 0) / attempts) if attempts else None,
        "avg_duration_ms": float(avg_ms) if avg_ms is not None else None,
        "recent_attempts": limit,
    }


# --- exercise quality ----------------------------------------------------------


def exercise_quality(db: Session, slug: str) -> dict:
    """Content-quality signals for one exercise. Every number is a real
    aggregate; gaps are reported as null/insufficient, never invented."""
    exercise = db.get(Exercise, slug)
    if exercise is None and slug not in registry.registered_slugs():
        raise ValueError("exercise_not_found")

    supply_rows = (
        db.query(Puzzle.status, func.count(Puzzle.id))
        .filter(Puzzle.exercise_slug == slug)
        .group_by(Puzzle.status)
        .all()
    )
    by_status = {status: int(count) for status, count in supply_rows}
    published = by_status.get(STATUS_PUBLISHED, 0)
    review_backlog = sum(
        by_status.get(status, 0)
        for status in (STATUS_VALIDATED, STATUS_REVIEWED, STATUS_APPROVED)
    )
    quarantined = by_status.get("quarantined", 0)

    difficulty_rows = (
        db.query(Puzzle.difficulty, func.count(Puzzle.id))
        .filter(Puzzle.exercise_slug == slug, Puzzle.status == STATUS_PUBLISHED)
        .group_by(Puzzle.difficulty)
        .all()
    )
    difficulty_distribution = [
        {"difficulty": difficulty, "count": int(count)} for difficulty, count in difficulty_rows
    ]
    covered_levels = {row[0] for row in difficulty_rows if row[0] is not None}

    validation_failures = (
        db.query(func.count(PuzzleValidation.id))
        .join(Puzzle, Puzzle.id == PuzzleValidation.puzzle_id)
        .filter(Puzzle.exercise_slug == slug, PuzzleValidation.status == "fail")
        .scalar()
        or 0
    )

    # High-failure published puzzles (>=5 attempts, >=70% non-correct).
    attempt_rows = (
        db.query(
            Attempt.puzzle_id,
            func.count(Attempt.id).label("attempts"),
            func.sum(case((Attempt.result == "correct", 1), else_=0)).label("correct"),
        )
        .join(Puzzle, Puzzle.id == Attempt.puzzle_id)
        .filter(Puzzle.exercise_slug == slug, Puzzle.status == STATUS_PUBLISHED)
        .group_by(Attempt.puzzle_id)
        .having(func.count(Attempt.id) >= 5)
        .all()
    )
    high_failure = [
        {"puzzle_id": int(pid), "attempts": int(attempts),
         "failure_rate": round((int(attempts) - int(correct or 0)) / int(attempts), 4)}
        for pid, attempts, correct in attempt_rows
        if attempts and (int(attempts) - int(correct or 0)) / int(attempts) >= 0.7
    ]

    perf = (
        db.query(
            func.count(Attempt.id),
            func.sum(case((Attempt.result == "correct", 1), else_=0)),
            func.avg(Attempt.duration_ms),
        )
        .filter(Attempt.exercise_slug == slug)
        .first()
    )
    attempts_total = int(perf[0] or 0)
    correct_total = int(perf[1] or 0)

    reasons: list[str] = []
    if published < admin_service.LOW_SUPPLY_THRESHOLD:
        reasons.append("low_supply")
    if review_backlog > 0:
        reasons.append("review_backlog")
    if quarantined > 0:
        reasons.append("quarantined_content")
    if int(validation_failures) > 0:
        reasons.append("validation_failures")
    if high_failure:
        reasons.append("high_failure_puzzles")
    if len(covered_levels) < 3:
        reasons.append("thin_difficulty_coverage")

    return {
        "exercise_slug": slug,
        "supply_by_status": [{"status": s, "count": c} for s, c in sorted(by_status.items())],
        "published": published,
        "review_backlog": review_backlog,
        "quarantined": quarantined,
        "difficulty_distribution": difficulty_distribution,
        "difficulty_levels_covered": sorted(covered_levels),
        "validation_failures": int(validation_failures),
        "high_failure_puzzles": sorted(high_failure, key=lambda r: r["failure_rate"], reverse=True)[
            :10
        ],
        "attempts": attempts_total,
        "success_rate": (correct_total / attempts_total) if attempts_total else None,
        "avg_duration_ms": float(perf[2]) if perf[2] is not None else None,
        "supply_state": (
            "critical" if published == 0
            else "attention" if reasons else "healthy"
        ),
        "attention_reasons": reasons,
    }


# --- exercise learning ---------------------------------------------------------


def exercise_learning(db: Session, slug: str, *, days: int = 30) -> dict:
    """Learning/usage signals for one exercise, recomputed from durable
    rows (attempts, evidence, adaptive recommendations). Read-only."""
    from app.modules.adaptive.models import AdaptiveRecommendation
    from app.modules.evidence.models import Evidence

    exercise = db.get(Exercise, slug)
    if exercise is None and slug not in registry.registered_slugs():
        raise ValueError("exercise_not_found")
    since = _utcnow() - timedelta(days=days)

    usage = (
        db.query(
            func.count(Attempt.id),
            func.sum(case((Attempt.result == "correct", 1), else_=0)),
            func.count(func.distinct(Attempt.user_id)),
            func.avg(Attempt.duration_ms),
        )
        .filter(Attempt.exercise_slug == slug, Attempt.created_at >= since)
        .first()
    )
    attempts_total = int(usage[0] or 0)

    by_result = (
        db.query(Attempt.result, func.count(Attempt.id))
        .filter(Attempt.exercise_slug == slug, Attempt.created_at >= since)
        .group_by(Attempt.result)
        .all()
    )

    mistake_rows = (
        db.query(Evidence.mistake_core, func.count(Evidence.id))
        .filter(Evidence.exercise_slug == slug, Evidence.observed_at >= since)
        .group_by(Evidence.mistake_core)
        .order_by(func.count(Evidence.id).desc())
        .limit(10)
        .all()
    )
    skill_rows = (
        db.query(Evidence.skill_key, Evidence.direction, func.count(Evidence.id))
        .filter(Evidence.exercise_slug == slug, Evidence.observed_at >= since)
        .group_by(Evidence.skill_key, Evidence.direction)
        .order_by(func.count(Evidence.id).desc())
        .limit(20)
        .all()
    )
    rec_rows = (
        db.query(AdaptiveRecommendation.status, func.count(AdaptiveRecommendation.id))
        .filter(
            AdaptiveRecommendation.exercise_slug == slug,
            AdaptiveRecommendation.created_at >= since,
        )
        .group_by(AdaptiveRecommendation.status)
        .all()
    )

    primary = evidence_taxonomy.primary_skill(slug)
    secondaries = [
        {"skill": skill, "link": link}
        for skill, link in evidence_taxonomy.secondary_skills(slug)
    ]
    return {
        "exercise_slug": slug,
        "window_days": days,
        "usage": {
            "attempts": attempts_total,
            "correct": int(usage[1] or 0),
            "success_rate": (int(usage[1] or 0) / attempts_total) if attempts_total else None,
            "active_users": int(usage[2] or 0),
            "avg_duration_ms": float(usage[3]) if usage[3] is not None else None,
            "by_result": [{"result": r, "count": int(c)} for r, c in by_result],
        },
        "mistakes": [{"mistake": m or "none", "count": int(c)} for m, c in mistake_rows],
        "skills": {
            "primary": primary,
            "secondary": secondaries,
            "evidence": [
                {"skill_key": s or "none", "direction": d or "unknown", "count": int(c)}
                for s, d, c in skill_rows
            ],
        },
        "recommendations": [{"status": s, "count": int(c)} for s, c in rec_rows],
    }


# --- global content health -----------------------------------------------------


def content_health(db: Session) -> dict:
    """Global supply view: one row per catalog exercise with the reason
    it needs attention. Thresholds reuse the product constants."""
    stats = admin_service.exercise_supply_stats(db)
    generators_by_exercise: dict[str, list[str]] = {}
    for definition in generator_service.available_generators():
        generators_by_exercise.setdefault(definition.exercise_slug, []).append(definition.code)

    rows = []
    for exercise in db.query(Exercise).order_by(Exercise.sort_order, Exercise.slug).all():
        entry = stats["supply"].get(
            exercise.slug, {"published": 0, "needs_review": 0, "total": 0, "by_status": {}}
        )
        perf = stats["performance"].get(exercise.slug, {"attempts": 0, "success_rate": None})
        published = entry["published"]
        needs_review = entry["needs_review"]
        by_status = entry.get("by_status", {})
        reasons: list[str] = []
        if published < admin_service.LOW_SUPPLY_THRESHOLD:
            reasons.append("low_supply")
        if needs_review > 0:
            reasons.append("review_backlog")
        if by_status.get("quarantined", 0):
            reasons.append("quarantined_content")
        if exercise.slug not in generators_by_exercise:
            reasons.append("no_generator")
        state = "healthy" if not reasons else ("critical" if published == 0 else "attention")
        rows.append(
            {
                "slug": exercise.slug,
                "title_fa": exercise.title_fa,
                "is_active": bool(exercise.is_active),
                "published": published,
                "total": entry["total"],
                "needs_review": needs_review,
                "quarantined": by_status.get("quarantined", 0),
                "attempts": perf["attempts"],
                "success_rate": perf["success_rate"],
                "generator_available": exercise.slug in generators_by_exercise,
                "generator_codes": generators_by_exercise.get(exercise.slug, []),
                "supply_state": state,
                "reasons": reasons,
            }
        )
    attention = sum(1 for row in rows if row["supply_state"] != "healthy")
    return {
        "low_supply_threshold": admin_service.LOW_SUPPLY_THRESHOLD,
        "exercises": rows,
        "attention_count": attention,
    }
