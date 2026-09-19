"""Recommendation engine (P7): suitable Exercise / Puzzle selection.

Priority (DEC-010 direct work first, DEC-009 suitability over hardest):

```text
Direct Coach Assignment
        ↓
Recommendation Engine
        ↓
Exercise / Puzzle
```

Read-only and deterministic. This module never writes: no attempts, no
evidence, no skill-state, no mastery, no rating, and no recommendation
rows are created (same precedent as skill_state / mastery / analytics:
recompute from authoritative state on read). A repeated call over
unchanged state returns the identical recommendation.

Authoritative inputs (canonical, never reinvented here):

* ``assignments`` — open (``assigned``) direct coach rows override the
  engine. Lifecycle/safety still apply: an assignment naming an
  unknown/disabled exercise or with no servable puzzle is skipped, and
  the engine is tried next.
* ``skill_state`` — per-skill levels (struggling first).
* ``mastery`` — per-skill mastery (mastered skills are deprioritized;
  skills without sufficient evidence are never treated as mastered:
  they surface as ``unknown`` and fall into the cold-start bucket).
* ``rating_engine`` — per-exercise ability for difficulty matching
  (``INITIAL_RATING`` default, same as adaptive).
* ``player_external_identities`` — placement signal only (DEC-005):
  used as the ability fallback solely when the exercise has no rating
  row yet. It never gates eligibility and never overrides behavioral
  evidence.
* ``attempts`` — the owner's history (recent-puzzle avoidance +
  exercise tie-break). Speed (``duration_ms``) is never read: speed is
  assessment/fun signal, never a rating or recommendation signal
  (DEC-009).
* ``puzzles`` / ``exercises`` — servability (see below).

Servability (single choke point ``eligible_puzzles``): a puzzle is
servable exactly when ``status == "published"`` with the
player-visibility projection in sync (``is_published`` True,
``is_archived`` False). Every other lifecycle state — ``draft``,
``validated``, ``reviewed``, ``approved``, ``quarantined``,
``retired``, ``rejected`` — is excluded, plus the submit-time safety
rule (quarantined/rejected never servable even if flags desync) and
disabled exercises (Phase 6 rule). Deleted puzzles (no row) cannot be
returned by construction.

Documented choices (the docs specify no numerics, so the smallest
deterministic rules reusing established precedents are used):

* ``RECENCY_EXCLUSION = 20`` — the owner's 20 most recent attempted
  puzzle ids are avoided (adaptive ``RECENCY_EXCLUSION`` precedent).
  When an exercise has servable puzzles but all were recently seen,
  recency relaxes to the least-recently-attempted one (flagged
  ``fallback_recency``) rather than stranding the learner (adaptive
  fallback precedent). Lifecycle rules never relax.
* Exercise buckets (priority order; first bucket with servable content
  wins, so no weights or scores are invented):
  ``struggling`` skill -> ``emerging``/``developing`` skill or mastery
  -> no evidence (cold start) -> ``proficient`` -> ``mastered``.
  Within a bucket: fewer own attempts first, then slug (both
  deterministic). Unmapped exercises (no canonical primary skill) join
  the cold-start bucket: they are never assumed mastered.
* Ability per exercise: current rating, else clamped external rating
  (``[RATING_MIN, RATING_MAX]`` bounds reused) when present, else
  ``INITIAL_RATING``. The external value only moves the difficulty
  target; it excludes nothing.
* Puzzle pick: closest ``initial_rating`` to ability, id tie-break. No
  randomness, no seed: output is fully deterministic.

Reasons (machine-readable, internal trace only — no user-facing
numeric ranking or score is produced):

* ``DIRECT_ASSIGNMENT`` — open direct coach assignment served.
* ``WEAK_SKILL`` / ``DEVELOPING_SKILL`` / ``COLD_START`` /
  ``APPROPRIATE_DIFFICULTY`` / ``REVIEW_MASTERED`` — engine buckets.

Out of scope (explicit non-goals): persistence, API/UI, spacing
schedules, ML ranking, coach-issued system recommendations, and any
change to P1-P6 behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evidence import taxonomy as tx
from app.modules.exercises.models import Exercise
from app.modules.mastery import service as mastery_service
from app.modules.player.models import PlayerExternalIdentity
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import (
    STATUS_PUBLISHED,
    STATUS_QUARANTINED,
    STATUS_REJECTED,
    Puzzle,
)
from app.modules.rating_engine.service import (
    INITIAL_RATING,
    RATING_MAX,
    RATING_MIN,
    get_rating,
)
from app.modules.relationships.models import (
    ASSIGNMENT_ASSIGNED,
    Assignment,
)
from app.modules.skill_state import service as skill_state_service

# --- reasons (machine-readable, internal trace only) --------------------------

REASON_DIRECT_ASSIGNMENT = "DIRECT_ASSIGNMENT"
REASON_WEAK_SKILL = "WEAK_SKILL"
REASON_DEVELOPING_SKILL = "DEVELOPING_SKILL"
REASON_COLD_START = "COLD_START"
REASON_APPROPRIATE = "APPROPRIATE_DIFFICULTY"
REASON_REVIEW_MASTERED = "REVIEW_MASTERED"

REASONS = frozenset(
    {
        REASON_DIRECT_ASSIGNMENT,
        REASON_WEAK_SKILL,
        REASON_DEVELOPING_SKILL,
        REASON_COLD_START,
        REASON_APPROPRIATE,
        REASON_REVIEW_MASTERED,
    }
)

# --- policy knobs (documented choices; see module docstring) ------------------

# Own recent attempts whose puzzles are avoided (adaptive precedent).
RECENCY_EXCLUSION = 20


@dataclass(frozen=True)
class Recommendation:
    """One deterministic recommendation (read-only derivation)."""

    exercise_slug: str
    puzzle_id: int | None
    reason: str
    assignment_id: int | None = None
    trace: dict[str, Any] = field(default_factory=dict)


def eligible_puzzles(db: Session, exercise_slug: str) -> list[Puzzle]:
    """Servable puzzles of one exercise, id-ordered.

    Exactly ``published`` + projection in sync. Every other lifecycle
    state is excluded; quarantined/rejected are additionally guarded
    explicitly (submit-time safety precedent) so a flag desync can
    never leak them into recommendations. Disabled exercises yield
    nothing (Phase 6 rule); a missing catalog row stays selectable so
    legacy playable content is not silently dropped (submit precedent).
    """
    exercise = db.get(Exercise, exercise_slug)
    if exercise is not None and not exercise.is_active:
        return []
    rows = (
        db.query(Puzzle)
        .filter(Puzzle.exercise_slug == exercise_slug)
        .order_by(Puzzle.id)
        .all()
    )
    out = []
    for row in rows:
        if row.status != STATUS_PUBLISHED:
            continue
        if row.status in (STATUS_QUARANTINED, STATUS_REJECTED):
            continue  # pragma: no cover - unreachable while above holds; belt and braces
        if not row.is_published or row.is_archived:
            continue
        out.append(row)
    return out


def _recent_puzzle_ids(db: Session, user_id: int, limit: int = RECENCY_EXCLUSION) -> list[int]:
    rows = (
        db.query(Attempt.puzzle_id)
        .filter(Attempt.user_id == int(user_id))
        .order_by(Attempt.id.desc())
        .limit(limit)
        .all()
    )
    return [pid for (pid,) in rows if pid is not None]


def _attempt_counts(db: Session, user_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    rows = db.query(Attempt.exercise_slug).filter(Attempt.user_id == int(user_id)).all()
    for (slug,) in rows:
        counts[slug] = counts.get(slug, 0) + 1
    return counts


def _last_attempt_id_per_puzzle(db: Session, user_id: int) -> dict[int, int]:
    """Puzzle id -> owner's most recent attempt id (for recency relaxation)."""
    rows = (
        db.query(Attempt.puzzle_id, Attempt.id)
        .filter(Attempt.user_id == int(user_id))
        .order_by(Attempt.id.desc())
        .all()
    )
    last: dict[int, int] = {}
    for pid, aid in rows:
        if pid is not None and pid not in last:
            last[pid] = aid
    return last


def _placement_rating(db: Session, user_id: int) -> float | None:
    """External rating as placement signal (DEC-005), or None.

    The strongest self-reported external rating across providers. Never
    a gate: callers use it only as an ability fallback when no rating
    row exists yet.
    """
    rows = (
        db.query(PlayerExternalIdentity.rating)
        .filter(PlayerExternalIdentity.user_id == int(user_id))
        .all()
    )
    values = [r for (r,) in rows if isinstance(r, (int, float))]
    if not values:
        return None
    return float(max(min(max(values), RATING_MAX), RATING_MIN))


def ability_for(db: Session, user_id: int, exercise_slug: str) -> tuple[float, bool]:
    """(ability, placement_used) for difficulty matching.

    Current rating wins whenever a row exists (behavioral evidence
    outweighs external signals per DEC-005); otherwise the external
    placement rating, otherwise ``INITIAL_RATING``.
    """
    row = get_rating(db, int(user_id), exercise_slug)
    if row is not None:
        return float(row.rating), False
    placement = _placement_rating(db, int(user_id))
    if placement is not None:
        return placement, True
    return float(INITIAL_RATING), False


def _pick_puzzle(
    candidates: list[Puzzle],
    *,
    ability: float,
    recent_ids: set[int],
    last_seen: dict[int, int],
) -> tuple[Puzzle | None, bool]:
    """Deterministic pick: closest rating to ability, id tie-break.

    Recently-seen puzzles are avoided; when everything was seen,
    recency relaxes to the least-recently-attempted candidate
    (``fallback_recency=True``) rather than stranding the learner.
    """
    if not candidates:
        return None, False
    fresh = [p for p in candidates if p.id not in recent_ids]
    pool = fresh if fresh else candidates
    fallback = not fresh
    if fallback:
        pool = sorted(pool, key=lambda p: (last_seen.get(p.id, 0), abs((p.initial_rating or 0) - ability), p.id or 0))
        return pool[0], True
    best = min(pool, key=lambda p: (abs((p.initial_rating or 0) - ability), p.id or 0))
    return best, False


def _bucket_for(primary_skill: str | None, state, mastery: dict) -> tuple[int, str]:
    """(bucket, reason) for one exercise from its primary skill signals.

    Unmapped exercises (no canonical primary skill) join the cold-start
    bucket: without evidence they can never be assumed mastered.
    """
    if primary_skill is None:
        return 2, REASON_COLD_START
    level = state.skills[primary_skill].level
    status = mastery[primary_skill].status
    if level == skill_state_service.LEVEL_STRUGGLING:
        return 0, REASON_WEAK_SKILL
    if (
        status in (mastery_service.STATUS_EMERGING, mastery_service.STATUS_DEVELOPING)
        or level
        in (
            skill_state_service.LEVEL_EMERGING,
            skill_state_service.LEVEL_DEVELOPING,
        )
    ):
        return 1, REASON_DEVELOPING_SKILL
    if status == mastery_service.STATUS_UNKNOWN or level == skill_state_service.LEVEL_UNSEEN:
        return 2, REASON_COLD_START
    if status == mastery_service.STATUS_MASTERED:
        return 4, REASON_REVIEW_MASTERED
    return 3, REASON_APPROPRIATE


def _open_assignments(db: Session, user_id: int) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(
            Assignment.student_user_id == int(user_id),
            Assignment.status == ASSIGNMENT_ASSIGNED,
        )
        .order_by(Assignment.id)
        .all()
    )


def recommend_for_user(db: Session, user_id: int) -> Recommendation | None:
    """Deterministic recommendation for one account. Read-only.

    Direct open coach assignments override the engine (first eligible
    in id order wins); otherwise the engine picks by skill/mastery
    buckets then ability-relative puzzle ranking. Returns None when no
    servable content exists for the user.
    """
    uid = int(user_id)
    recent = set(_recent_puzzle_ids(db, uid))
    last_seen = _last_attempt_id_per_puzzle(db, uid)
    counts = _attempt_counts(db, uid)
    skipped_assignments: list[dict[str, Any]] = []
    skipped_exercises: list[dict[str, Any]] = []

    # --- direct assignment override (lifecycle/safety still enforced) --------
    for row in _open_assignments(db, uid):
        candidates = eligible_puzzles(db, row.exercise_slug)
        if not candidates:
            skipped_assignments.append({"assignment_id": row.id, "why": "no_eligible_content"})
            continue
        ability, placement_used = ability_for(db, uid, row.exercise_slug)
        picked, fallback = _pick_puzzle(
            candidates, ability=ability, recent_ids=recent, last_seen=last_seen
        )
        if picked is None:  # pragma: no cover - candidates non-empty
            continue
        return Recommendation(
            exercise_slug=row.exercise_slug,
            puzzle_id=picked.id,
            reason=REASON_DIRECT_ASSIGNMENT,
            assignment_id=row.id,
            trace={
                "reason": REASON_DIRECT_ASSIGNMENT,
                "assignment_id": row.id,
                "placement_used": placement_used,
                "fallback_recency": fallback,
                "skipped_assignments": skipped_assignments,
            },
        )

    # --- engine ---------------------------------------------------------------
    state = skill_state_service.skill_state_for_user(db, uid)
    mastery = mastery_service.mastery_for_user(db, uid)
    slugs = sorted({s for (s,) in db.query(Puzzle.exercise_slug).all()})
    ranked: list[tuple[tuple, str, str]] = []
    for slug in slugs:
        bucket, reason = _bucket_for(tx.primary_skill(slug), state, mastery)
        ranked.append(((bucket, counts.get(slug, 0), slug), slug, reason))
    ranked.sort(key=lambda item: item[0])

    placement_used_any = False
    fallback_any = False
    for _, slug, reason in ranked:
        candidates = eligible_puzzles(db, slug)
        if not candidates:
            skipped_exercises.append({"exercise": slug, "why": "no_eligible_content"})
            continue
        ability, placement_used = ability_for(db, uid, slug)
        placement_used_any = placement_used_any or placement_used
        picked, fallback = _pick_puzzle(
            candidates, ability=ability, recent_ids=recent, last_seen=last_seen
        )
        if picked is None:  # pragma: no cover - candidates non-empty
            continue
        fallback_any = fallback_any or fallback
        return Recommendation(
            exercise_slug=slug,
            puzzle_id=picked.id,
            reason=reason,
            assignment_id=None,
            trace={
                "reason": reason,
                "assignment_id": None,
                "placement_used": placement_used,
                "fallback_recency": fallback,
                "skipped_exercises": skipped_exercises,
            },
        )
    if skipped_assignments or skipped_exercises:
        return None
    return None
