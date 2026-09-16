"""Evidence generation service (P2).

``generate_for_attempt`` runs inside ``progress.service.submit_attempt``
in the same transaction: attempt + evidence commit atomically, and a
rolled back attempt leaves no orphan evidence. Flushes, never commits.

Idempotency: when rows already exist for the attempt, they are
returned unchanged (reprocessing can never duplicate evidence; the
``(attempt_id, evidence_key)`` unique constraint backstops races).

Repeat detection (``repeated-mistake``): after persisting the base
drafts, one bounded indexed query checks the owner's recent evidence
for the same skill + mistake. A hit appends a single strengthened
negative row. No full-history scans, no N+1s. When recurrence cannot
be established, only the base mistake is stored (never falsely
labeled). Time-window generalization belongs to P3 (``observed_at``
is persisted for it).

Rating is untouched: mistakes feed evidence only, never rating deltas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evidence import classify as clf
from app.modules.evidence import taxonomy as tx
from app.modules.evidence.classify import MistakeDraft
from app.modules.evidence.models import Evidence

# Bounded repeat lookup: recurrence is checked against this many of the
# owner's most recent evidence rows (same skill). Plenty for ~150 active
# students; P3 generalizes windows with observed_at when data demands it.
REPEAT_LOOKUP_LIMIT = 20


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def evidence_key_for(draft: MistakeDraft) -> str:
    """Deterministic identity of one draft within its attempt."""
    return ":".join(
        [
            draft.direction[:3],
            draft.mistake_core or "outcome",
            draft.mistake_specific or "-",
            draft.role,
            draft.skill or "-",
        ]
    )


def repeat_evidence_key(*, skill: str, core: str, specific: str | None) -> str:
    return ":".join(["neg", tx.REPEATED_MISTAKE, specific or core, tx.ROLE_PRIMARY, skill])


def existing_for_attempt(db: Session, attempt_id: int) -> list[Evidence]:
    return (
        db.query(Evidence)
        .filter(Evidence.attempt_id == attempt_id)
        .order_by(Evidence.id)
        .all()
    )


def _base_context(
    *, attempt, result: str, detail: dict[str, Any], hints_used: list[str]
) -> dict[str, Any]:
    _correct, missed, wrong = (
        detail.get("correct") if isinstance(detail.get("correct"), list) else [],
        detail.get("missed") if isinstance(detail.get("missed"), list) else [],
        detail.get("wrong") if isinstance(detail.get("wrong"), list) else [],
    )
    context: dict[str, Any] = {
        "mode": attempt.mode,
        "result": result,
        "exercise_slug": attempt.exercise_slug,
        "puzzle_id": attempt.puzzle_id,
        "has_hints": bool(hints_used),
        "hints_count": len(hints_used),
        "duration_ms": attempt.duration_ms,
        "n_correct": len(_correct or []),
        "n_missed": len(missed or []),
        "n_wrong": len(wrong or []),
        "puzzle_rating_snapshot": attempt.puzzle_rating_snapshot,
        "difficulty_snapshot": attempt.difficulty_snapshot,
    }
    return {k: v for k, v in context.items() if v is not None or k in ("duration_ms",)}


def _find_repeat(
    db: Session,
    *,
    owner_user_id: int | None,
    owner_guest_id: int | None,
    attempt_id: int,
    skill: str,
    core: str,
    specific: str | None,
) -> Evidence | None:
    """Most recent matching evidence row, if the pattern already exists.

    Same owner + same skill + same mistake identity (specific when the
    base row names one, else core), excluding the current attempt. One
    bounded indexed query.
    """
    query = db.query(Evidence).filter(
        Evidence.skill_key == skill,
        Evidence.attempt_id != attempt_id,
        Evidence.direction == tx.DIRECTION_NEGATIVE,
    )
    if owner_user_id is not None:
        query = query.filter(Evidence.user_id == owner_user_id)
    elif owner_guest_id is not None:
        query = query.filter(Evidence.guest_session_id == owner_guest_id)
    else:  # pragma: no cover - attempts always carry exactly one owner
        return None
    query = query.order_by(Evidence.id.desc()).limit(REPEAT_LOOKUP_LIMIT)
    identity = specific or core
    for row in query.all():
        if (row.mistake_specific or row.mistake_core) == identity:
            return row
    return None


def generate_for_attempt(
    db: Session,
    *,
    attempt,
    result: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[Evidence]:
    """Classify one submitted attempt and persist its evidence rows.

    Idempotent: existing rows for the attempt are returned as-is.
    Flushes (no commit): the caller owns the transaction boundary.
    Classification never raises out of ``classify``; only persistence
    errors propagate, and then the whole submission rolls back
    consistently (attempt included — evidence can never silently
    contradict a stored attempt outcome).
    """
    stored = existing_for_attempt(db, attempt.id)
    if stored:
        return stored

    detail = dict(detail) if isinstance(detail, dict) else {}
    raw_answer = raw_answer if isinstance(raw_answer, dict) else {}
    hints_used = (
        [h for h in hints_used if isinstance(h, str)] if isinstance(hints_used, list) else []
    )

    drafts = clf.classify(
        exercise_slug=attempt.exercise_slug,
        result=result,
        detail=detail,
        raw_answer=raw_answer,
        puzzle_answer=puzzle_answer if isinstance(puzzle_answer, dict) else {},
        hints_used=hints_used,
    )

    observed_at = attempt.created_at or _utcnow_naive()
    base_context = _base_context(
        attempt=attempt, result=result, detail=detail, hints_used=hints_used
    )
    rows: list[Evidence] = []
    for draft in drafts:
        context = dict(base_context)
        context.update(draft.context)
        rows.append(
            Evidence(
                attempt_id=attempt.id,
                user_id=attempt.user_id,
                guest_session_id=attempt.guest_session_id,
                exercise_slug=attempt.exercise_slug,
                puzzle_id=attempt.puzzle_id,
                source=tx.SOURCE_ATTEMPT,
                skill_key=draft.skill,
                skill_role=draft.role,
                mistake_core=draft.mistake_core,
                mistake_specific=draft.mistake_specific,
                direction=draft.direction,
                strength=draft.strength,
                confidence=draft.confidence,
                context_json=context,
                evidence_key=evidence_key_for(draft),
                observed_at=observed_at,
            )
        )
    db.add_all(rows)
    db.flush()

    # Repeat detection over the first negative primary draft only:
    # recurrence upgrades strength once; secondaries inherit via linkage.
    base_negative = next(
        (
            d
            for d in drafts
            if d.direction == tx.DIRECTION_NEGATIVE
            and d.role == tx.ROLE_PRIMARY
            and d.skill
            and d.mistake_core
            and d.mistake_core != tx.REPEATED_MISTAKE
        ),
        None,
    )
    if base_negative is not None and base_negative.skill and base_negative.mistake_core:
        prior = _find_repeat(
            db,
            owner_user_id=attempt.user_id,
            owner_guest_id=attempt.guest_session_id,
            attempt_id=attempt.id,
            skill=base_negative.skill,
            core=base_negative.mistake_core,
            specific=base_negative.mistake_specific,
        )
        if prior is not None:
            key = repeat_evidence_key(
                skill=base_negative.skill,
                core=base_negative.mistake_core,
                specific=base_negative.mistake_specific,
            )
            context = dict(base_context)
            context["repeats_attempt_id"] = prior.attempt_id
            context["repeated_mistake"] = (
                base_negative.mistake_specific or base_negative.mistake_core
            )
            repeat_row = Evidence(
                attempt_id=attempt.id,
                user_id=attempt.user_id,
                guest_session_id=attempt.guest_session_id,
                exercise_slug=attempt.exercise_slug,
                puzzle_id=attempt.puzzle_id,
                source=tx.SOURCE_ATTEMPT,
                skill_key=base_negative.skill,
                skill_role=tx.ROLE_PRIMARY,
                mistake_core=tx.REPEATED_MISTAKE,
                mistake_specific=base_negative.mistake_specific,
                direction=tx.DIRECTION_NEGATIVE,
                strength=tx.STRENGTH_STRONG,
                confidence=tx.CONFIDENCE_HIGH,
                context_json=context,
                evidence_key=key,
                observed_at=observed_at,
            )
            # Defensive against double-insert races: the unique
            # (attempt_id, evidence_key) constraint is authoritative.
            if not any(r.evidence_key == key for r in rows):
                rows.append(repeat_row)
                db.add(repeat_row)
                db.flush()

    return rows
