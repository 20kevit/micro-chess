"""Skill state aggregation (P3): Evidence -> per-skill levels + overall.

Read-only and deterministic. Evidence rows are the sole source: this
module never writes, never reclassifies, and never touches P2 code.
History-aware means the full append-only history is summed on every
call (no windows, no decay) in ``(observed_at, id)`` order, so a
recomputation over the same rows always yields the same state.

Authoritative inputs (canonical, not invented here):

* ``taxonomy.SKILLS`` — the 18 canonical skills. Rows naming any other
  skill (e.g. an unmapped exercise slug carried as fallback) are
  ignored: only canonical skills can hold state.
* ``taxonomy`` ordinals — direction / strength / confidence / role.

Relevance rule (from the taxonomy docstrings):

* Only rows with a canonical ``skill_key``, ``skill_role`` in
  ``(primary, secondary)`` and ``direction`` in ``(positive,
  negative)`` move estimates.
* Neutral rows (malformed input, inefficiency notes on correct solves,
  unclassified, invalid content) are excluded by construction.
* ``no-response`` rows carry no skill (``skill_key IS NULL``,
  ``role == "none"``), so they are excluded by construction: an
  effort signal is never treated as skill weakness.

Point model (documented choice — the docs specify no numerics, so the
smallest integer rank-order mapping is used; these are ordinal ranks,
not calibrated severities):

* sign: positive ``+1`` / negative ``-1``.
* strength: weak ``1``, direct ``2``, strong ``3``.
* role: primary ``2``, secondary ``1`` (secondary strictly less, per
  the taxonomy guardrail; never equal weight).
* confidence: high ``2``, medium ``1``, low ``0`` (a low-confidence
  row carries no claim).
* ``points = sign * strength * role * confidence``.
* Reference unit: one clean primary demonstration (positive,
  direct, high, primary) = ``+8`` points; ``units = points / 8``.

Per-skill level from net ``units`` (coarse counts of net clean
demonstrations — the docs specify no thresholds, so these count-based
bands are the simplest explainable choice):

* no relevant rows -> ``unseen`` (excluded from the overall).
* ``units <= -1`` -> ``struggling``.
* ``-1 < units < 1`` -> ``emerging``.
* ``1 <= units < 3`` -> ``developing``.
* ``units >= 3`` -> ``proficient``.

Per-skill confidence (minimal volume gate — the docs specify none):

* ``low`` when fewer than 2 distinct attempts or ``|units| < 1``
  (thin or contradictory signal); ``unseen`` skills are ``low``.
* ``medium`` when fewer than 5 distinct attempts, else ``high``.

Overall (never a simple average; unseen skills never participate):

* Evidence-weighted mean of seen skills' units, each skill weighted
  by its total ``|points|`` volume, mapped through the same bands.
  A skill with far more evidence dominates; a single stray attempt
  cannot swing the whole picture, and skills without evidence cannot
  drag it.
* Overall confidence from total distinct attempts over seen skills:
  ``<3`` -> ``low``, ``<10`` -> ``medium``, else ``high``; no seen
  skills -> ``unseen`` / ``low``.

Out of scope (explicit non-goals): mastery, recommendation,
assignment, assessment, and any rating redesign. No persistence: state
is recomputed from evidence on read (same precedent as analytics,
which adds no tables).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.modules.evidence import taxonomy as tx

# --- point factors (ordinal ranks; see module docstring) ----------------------

_STRENGTH_FACTOR = {
    tx.STRENGTH_WEAK: 1,
    tx.STRENGTH_DIRECT: 2,
    tx.STRENGTH_STRONG: 3,
}

_ROLE_FACTOR = {
    tx.ROLE_PRIMARY: 2,
    tx.ROLE_SECONDARY: 1,
}

_CONFIDENCE_FACTOR = {
    tx.CONFIDENCE_HIGH: 2,
    tx.CONFIDENCE_MEDIUM: 1,
    tx.CONFIDENCE_LOW: 0,
}

#: Points of one clean primary demonstration; the unit of every band.
UNIT_POINTS = 8

# --- level vocabulary ---------------------------------------------------------

LEVEL_UNSEEN = "unseen"
LEVEL_STRUGGLING = "struggling"
LEVEL_EMERGING = "emerging"
LEVEL_DEVELOPING = "developing"
LEVEL_PROFICIENT = "proficient"

LEVELS = (
    LEVEL_UNSEEN,
    LEVEL_STRUGGLING,
    LEVEL_EMERGING,
    LEVEL_DEVELOPING,
    LEVEL_PROFICIENT,
)


@dataclass(frozen=True)
class SkillLevel:
    skill: str
    level: str
    confidence: str
    points: int
    units: float
    evidence_count: int
    attempts_count: int
    last_observed_at: Any = None


@dataclass(frozen=True)
class SkillState:
    skills: dict[str, SkillLevel] = field(default_factory=dict)
    overall_level: str = LEVEL_UNSEEN
    overall_confidence: str = tx.CONFIDENCE_LOW
    overall_units: float = 0.0
    skills_seen: int = 0


def is_relevant(row: Any) -> bool:
    """Whether one evidence row may move skill estimates."""
    skill = getattr(row, "skill_key", None)
    if skill not in tx.SKILLS:
        return False
    if getattr(row, "skill_role", None) not in (tx.ROLE_PRIMARY, tx.ROLE_SECONDARY):
        return False
    return getattr(row, "direction", None) in (
        tx.DIRECTION_POSITIVE,
        tx.DIRECTION_NEGATIVE,
    )


def points_for(row: Any) -> int:
    """Integer points of one row; 0 for irrelevant rows (never negative)."""
    if not is_relevant(row):
        return 0
    sign = 1 if getattr(row, "direction") == tx.DIRECTION_POSITIVE else -1
    strength = _STRENGTH_FACTOR.get(getattr(row, "strength"), 0)
    role = _ROLE_FACTOR.get(getattr(row, "skill_role"), 0)
    confidence = _CONFIDENCE_FACTOR.get(getattr(row, "confidence"), 0)
    return sign * strength * role * confidence


def level_for_units(units: float, *, has_evidence: bool) -> str:
    if not has_evidence:
        return LEVEL_UNSEEN
    if units <= -1.0:
        return LEVEL_STRUGGLING
    if units < 1.0:
        return LEVEL_EMERGING
    if units < 3.0:
        return LEVEL_DEVELOPING
    return LEVEL_PROFICIENT


def confidence_for_skill(attempts_count: int, units: float) -> str:
    if attempts_count < 2 or abs(units) < 1.0:
        return tx.CONFIDENCE_LOW
    if attempts_count < 5:
        return tx.CONFIDENCE_MEDIUM
    return tx.CONFIDENCE_HIGH


def aggregate(rows: Sequence[Any]) -> SkillState:
    """Pure deterministic fold of evidence rows into skill state."""
    def _order_key(r: Any) -> tuple:
        seen_at = getattr(r, "observed_at", None)
        return (seen_at is None, seen_at, getattr(r, "id", 0) or 0)

    ordered = sorted((r for r in rows if r is not None), key=_order_key)
    per_skill: dict[str, SkillLevel] = {}
    for skill in tx.SKILLS:
        relevant = [r for r in ordered if getattr(r, "skill_key", None) == skill and is_relevant(r)]
        points = sum(points_for(r) for r in relevant)
        units = points / UNIT_POINTS
        attempts = {getattr(r, "attempt_id", None) for r in relevant}
        attempts.discard(None)
        if relevant:
            last_seen = max(getattr(r, "observed_at", None) for r in relevant)
            level = level_for_units(units, has_evidence=True)
            confidence = confidence_for_skill(len(attempts), units)
        else:
            last_seen = None
            level = LEVEL_UNSEEN
            confidence = tx.CONFIDENCE_LOW
        per_skill[skill] = SkillLevel(
            skill=skill,
            level=level,
            confidence=confidence,
            points=points,
            units=units,
            evidence_count=len(relevant),
            attempts_count=len(attempts),
            last_observed_at=last_seen,
        )

    seen = [s for s in per_skill.values() if s.evidence_count > 0]
    if not seen:
        return SkillState(skills=per_skill)

    total_weight = sum(abs(s.points) for s in seen)
    if total_weight == 0:
        # All-zero net (e.g. only low-confidence rows slipped through is
        # impossible by construction, but guard the division anyway).
        overall_units = 0.0
    else:
        overall_units = sum(s.units * abs(s.points) for s in seen) / total_weight
    total_attempts = sum(s.attempts_count for s in seen)
    if total_attempts < 3:
        overall_confidence = tx.CONFIDENCE_LOW
    elif total_attempts < 10:
        overall_confidence = tx.CONFIDENCE_MEDIUM
    else:
        overall_confidence = tx.CONFIDENCE_HIGH
    return SkillState(
        skills=per_skill,
        overall_level=level_for_units(overall_units, has_evidence=True),
        overall_confidence=overall_confidence,
        overall_units=overall_units,
        skills_seen=len(seen),
    )


def _rows_for_owner(
    db: Session, *, user_id: int | None, guest_session_id: int | None
) -> list[Any]:
    from app.modules.evidence.models import Evidence

    query = db.query(Evidence)
    if user_id is not None:
        query = query.filter(Evidence.user_id == user_id)
    elif guest_session_id is not None:
        query = query.filter(Evidence.guest_session_id == guest_session_id)
    else:  # pragma: no cover - callers always pass exactly one owner
        return []
    return query.order_by(Evidence.observed_at, Evidence.id).all()


def skill_state_for_user(db: Session, user_id: int) -> SkillState:
    """Read-only skill state for one account. No flush, no commit."""
    return aggregate(_rows_for_owner(db, user_id=user_id, guest_session_id=None))


def skill_state_for_guest(db: Session, guest_session_id: int) -> SkillState:
    """Read-only skill state for one guest session. No flush, no commit."""
    return aggregate(_rows_for_owner(db, user_id=None, guest_session_id=guest_session_id))
