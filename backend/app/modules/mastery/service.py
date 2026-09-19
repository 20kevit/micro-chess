"""Skill mastery derivation (P4): Evidence -> Skill State -> Mastery.

Read-only and deterministic. Evidence rows are the sole source via
``skill_state`` aggregation; this module never writes, never
reclassifies, and never touches P2/P3 code. Per-skill mastery is
recomputed from history on every call (same precedent as skill_state
and analytics: no tables, no persistence).

Authoritative inputs (canonical, not invented here):

* ``skill_state.aggregate`` — per-skill ``units`` / ``confidence`` /
  ``attempts_count`` / ``last_observed_at``. Unit bands (1 and 3) and
  confidence gates (2 and 5 attempts) are reused unchanged.
* ``taxonomy.SKILLS`` — the 18 canonical skills. Only rows that are
  relevant per ``skill_state.is_relevant`` participate.
* Evidence ``context_json`` — ``scaffolded`` / ``has_hints`` /
  ``hints_count`` for the no-hint rule, ``difficulty_snapshot`` for
  the difficulty rule, ``observed_at`` / ``puzzle_id`` for
  spread/diversity/retention/recency.
* ``PRODUCT_SCOPE.md`` mastery states + ``GAMIFICATION.md`` exercise
  mastery (Not Started / Learning / Practicing / Proficient /
  Mastered) and ``DEC-008`` (never one attempt or one score).

Documented choices (the docs specify no numerics, so the smallest
count-based gates are used; every threshold below is a small integer
reusing a P3/adaptive precedent where one exists):

* Statuses: ``unknown`` (no relevant evidence), ``emerging`` (has
  evidence, gates unmet), ``developing``, ``proficient``, ``mastered``.
* Base estimate reuses P3 unit bands: developing needs ``units >= 1``,
  proficient/mastered need ``units >= 3`` (the P3 proficient band; no
  new unit threshold is invented for mastered — mastered differs by
  robustness gates, not by a higher point total).
* Volume: developing ``attempts >= 3`` (one past the P3 low-confidence
  gate of 2, so a single attempt or pair can never leave emerging);
  proficient ``attempts >= 5`` (the P3 high-confidence boundary);
  mastered ``attempts >= 8`` (high-confidence plus a full clean-recent
  window of 3 on top).
* Spread/diversity: proficient ``puzzles >= 2`` and ``days >= 2``;
  mastered ``puzzles >= 3``, ``days >= 3`` and ``difficulties >= 2``
  distinct difficulty values among clean positives.
* Difficulty: hardest clean positive ``difficulty_snapshot`` must be
  ``>= 2`` for proficient, ``>= 3`` for mastered (midpoint of the
  1-5 puzzle scale). Rows without a snapshot never satisfy the gate.
* Clean recent record: the last 2 (proficient) / 3 (mastered) relevant
  rows in ``(observed_at, id)`` order must all be positive; a single
  recent failure blocks promotion.
* No-hint: the same recent window must all be unhinted
  (``scaffolded``/``has_hints``/``hints_count`` all clear), plus at
  least 3 (proficient) / 5 (mastered) distinct hint-free positive
  attempts overall. Scaffolded positives still count in P3 units but
  never count as clean here.
* Confidence: developing needs ``units`` and volume only; proficient
  needs P3 confidence ``medium`` or ``high``; mastered needs ``high``.
* Retention: mastered needs ``span_days >= 7`` between first and last
  relevant evidence (reuses adaptive ``STALE_DAYS``: the skill
  survived a full stale gap).
* Recency: proficient/mastered need ``days_since_last <= 30`` where
  the reference is the owner's latest ``observed_at`` across all
  skills by default (deterministic; never wall-clock unless the
  caller passes an explicit ``now``). Stale skills cap at developing.
* A single attempt or a single evidence row can at most yield
  ``emerging`` (volume gates enforce this structurally).

Out of scope (explicit non-goals): rating, recommendation,
assignment, assessment, persistence, API/UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.modules.evidence import taxonomy as tx
from app.modules.skill_state import service as skill_state

# --- statuses ---------------------------------------------------------------

STATUS_UNKNOWN = "unknown"
STATUS_EMERGING = "emerging"
STATUS_DEVELOPING = "developing"
STATUS_PROFICIENT = "proficient"
STATUS_MASTERED = "mastered"

STATUSES = (
    STATUS_UNKNOWN,
    STATUS_EMERGING,
    STATUS_DEVELOPING,
    STATUS_PROFICIENT,
    STATUS_MASTERED,
)

# --- gates (documented choices; see module docstring) ------------------------

MIN_ATTEMPTS_DEVELOPING = 3
MIN_ATTEMPTS_PROFICIENT = 5
MIN_ATTEMPTS_MASTERED = 8

MIN_PUZZLES_PROFICIENT = 2
MIN_PUZZLES_MASTERED = 3

MIN_DAYS_PROFICIENT = 2
MIN_DAYS_MASTERED = 3

MIN_DIFFICULTIES_MASTERED = 2
MIN_DIFFICULTY_PROFICIENT = 2
MIN_DIFFICULTY_MASTERED = 3

RECENT_WINDOW_PROFICIENT = 2
RECENT_WINDOW_MASTERED = 3

MIN_CLEAN_PROFICIENT = 3
MIN_CLEAN_MASTERED = 5

# Retention: first-to-last span proving the skill survived over time.
# Reuses adaptive STALE_DAYS so "retained" means "outlived one stale gap".
MIN_SPAN_DAYS_MASTERED = 7
# Recency: promotion-gated skills must have been seen within a month of
# the reference time. Stale skills fall back to developing at best.
MAX_DAYS_SINCE_LAST = 30


@dataclass(frozen=True)
class SkillMastery:
    skill: str
    status: str
    units: float
    confidence: str
    attempts: int
    puzzles: int
    days: int
    span_days: int | None
    days_since_last: int | None
    clean_positives: int
    max_difficulty: int | None
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _context_of(row: Any) -> dict[str, Any]:
    context = getattr(row, "context_json", None)
    return dict(context) if isinstance(context, dict) else {}


def is_hinted(row: Any) -> bool:
    """Whether one evidence row involved scaffolding/hints."""
    context = _context_of(row)
    if context.get("scaffolded") is True:
        return True
    if context.get("has_hints") is True:
        return True
    hints_count = context.get("hints_count")
    if isinstance(hints_count, int) and hints_count > 0:
        return True
    if isinstance(hints_count, float) and hints_count > 0:
        return True
    return False


def difficulty_of(row: Any) -> int | None:
    """Difficulty snapshot of one row, or None when unknown."""
    context = _context_of(row)
    value = context.get("difficulty_snapshot")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _order_key(row: Any) -> tuple:
    seen_at = getattr(row, "observed_at", None)
    return (seen_at is None, seen_at, getattr(row, "id", 0) or 0)


def _distinct_days(rows: Sequence[Any]) -> set:
    days: set = set()
    for row in rows:
        seen_at = getattr(row, "observed_at", None)
        if isinstance(seen_at, datetime):
            days.add(seen_at.date())
    return days


def evaluate_skill(
    skill: str,
    skill_level: Any,
    rows: Sequence[Any],
    *,
    reference: datetime | None = None,
) -> SkillMastery:
    """Pure deterministic mastery of one skill.

    ``rows`` is the owner's full evidence history (any skills); only
    rows both naming ``skill`` and passing ``skill_state.is_relevant``
    participate. ``reference`` defaults to the latest ``observed_at``
    in ``rows`` so recency never depends on wall-clock time.
    """
    relevant = sorted(
        (
            r
            for r in rows
            if r is not None
            and getattr(r, "skill_key", None) == skill
            and skill_state.is_relevant(r)
        ),
        key=_order_key,
    )
    units = float(getattr(skill_level, "units", 0.0))
    confidence = str(getattr(skill_level, "confidence", tx.CONFIDENCE_LOW))

    if not relevant:
        return SkillMastery(
            skill=skill,
            status=STATUS_UNKNOWN,
            units=units,
            confidence=confidence,
            attempts=0,
            puzzles=0,
            days=0,
            span_days=None,
            days_since_last=None,
            clean_positives=0,
            max_difficulty=None,
            reasons=("no-evidence",),
        )

    attempts = {getattr(r, "attempt_id", None) for r in relevant}
    attempts.discard(None)
    n_attempts = len(attempts)
    puzzles = {getattr(r, "puzzle_id", None) for r in relevant}
    puzzles.discard(None)
    days = _distinct_days(relevant)

    positives = [r for r in relevant if getattr(r, "direction", None) == tx.DIRECTION_POSITIVE]
    clean_attempts = {
        getattr(r, "attempt_id", None)
        for r in positives
        if not is_hinted(r) and getattr(r, "attempt_id", None) is not None
    }
    difficulties = {
        d for r in positives if not is_hinted(r) for d in (difficulty_of(r),) if d is not None
    }
    max_difficulty = max(difficulties) if difficulties else None

    seen_dates = sorted(
        getattr(r, "observed_at", None) for r in relevant if isinstance(getattr(r, "observed_at", None), datetime)
    )
    span_days = (seen_dates[-1] - seen_dates[0]).days if len(seen_dates) >= 2 else 0

    last_observed = seen_dates[-1] if seen_dates else None
    if reference is None:
        all_seen = [
            getattr(r, "observed_at", None)
            for r in rows
            if isinstance(getattr(r, "observed_at", None), datetime)
        ]
        reference = max(all_seen) if all_seen else None
    if last_observed is not None and reference is not None:
        days_since_last = max(0, (reference - last_observed).days)
    else:
        days_since_last = None

    recent2 = relevant[-RECENT_WINDOW_PROFICIENT:]
    recent3 = relevant[-RECENT_WINDOW_MASTERED:]
    recent2_clean = all(
        getattr(r, "direction", None) == tx.DIRECTION_POSITIVE and not is_hinted(r)
        for r in recent2
    ) and len(recent2) == RECENT_WINDOW_PROFICIENT
    recent3_clean = all(
        getattr(r, "direction", None) == tx.DIRECTION_POSITIVE and not is_hinted(r)
        for r in recent3
    ) and len(recent3) == RECENT_WINDOW_MASTERED
    fresh = days_since_last is not None and days_since_last <= MAX_DAYS_SINCE_LAST

    # Mastered: strictest robustness on top of the P3 proficient band.
    mastered_reasons = _missing_mastered(
        units=units,
        confidence=confidence,
        attempts=n_attempts,
        puzzles=len(puzzles),
        days=len(days),
        difficulties=len(difficulties),
        max_difficulty=max_difficulty,
        clean=len(clean_attempts),
        recent_ok=recent3_clean,
        span_days=span_days if seen_dates else None,
        fresh=fresh,
    )
    if not mastered_reasons:
        return SkillMastery(
            skill=skill,
            status=STATUS_MASTERED,
            units=units,
            confidence=confidence,
            attempts=n_attempts,
            puzzles=len(puzzles),
            days=len(days),
            span_days=span_days if seen_dates else None,
            days_since_last=days_since_last,
            clean_positives=len(clean_attempts),
            max_difficulty=max_difficulty,
            reasons=(),
        )

    proficient_reasons = _missing_proficient(
        units=units,
        confidence=confidence,
        attempts=n_attempts,
        puzzles=len(puzzles),
        days=len(days),
        max_difficulty=max_difficulty,
        clean=len(clean_attempts),
        recent_ok=recent2_clean,
        fresh=fresh,
    )
    if not proficient_reasons:
        return SkillMastery(
            skill=skill,
            status=STATUS_PROFICIENT,
            units=units,
            confidence=confidence,
            attempts=n_attempts,
            puzzles=len(puzzles),
            days=len(days),
            span_days=span_days if seen_dates else None,
            days_since_last=days_since_last,
            clean_positives=len(clean_attempts),
            max_difficulty=max_difficulty,
            reasons=(),
        )

    developing_reasons = _missing_developing(
        units=units,
        attempts=n_attempts,
        positives=len({getattr(r, "attempt_id", None) for r in positives if getattr(r, "attempt_id", None) is not None}),
        clean=len(clean_attempts),
        last_positive=bool(relevant) and getattr(relevant[-1], "direction", None) == tx.DIRECTION_POSITIVE,
    )
    if not developing_reasons:
        capped = list(proficient_reasons)
        if not fresh:
            capped.append("stale")
        return SkillMastery(
            skill=skill,
            status=STATUS_DEVELOPING,
            units=units,
            confidence=confidence,
            attempts=n_attempts,
            puzzles=len(puzzles),
            days=len(days),
            span_days=span_days if seen_dates else None,
            days_since_last=days_since_last,
            clean_positives=len(clean_attempts),
            max_difficulty=max_difficulty,
            reasons=tuple(capped),
        )

    return SkillMastery(
        skill=skill,
        status=STATUS_EMERGING,
        units=units,
        confidence=confidence,
        attempts=n_attempts,
        puzzles=len(puzzles),
        days=len(days),
        span_days=span_days if seen_dates else None,
        days_since_last=days_since_last,
        clean_positives=len(clean_attempts),
        max_difficulty=max_difficulty,
        reasons=tuple(developing_reasons),
    )


def _missing_developing(
    *, units: float, attempts: int, positives: int, clean: int, last_positive: bool
) -> list[str]:
    missing: list[str] = []
    if units < 1.0:
        missing.append("units<1")
    if attempts < MIN_ATTEMPTS_DEVELOPING:
        missing.append("volume<3")
    if positives < 2:
        missing.append("positives<2")
    if clean < 1:
        missing.append("no-clean-positive")
    if not last_positive:
        missing.append("recent-failure")
    return missing


def _missing_proficient(
    *,
    units: float,
    confidence: str,
    attempts: int,
    puzzles: int,
    days: int,
    max_difficulty: int | None,
    clean: int,
    recent_ok: bool,
    fresh: bool,
) -> list[str]:
    missing: list[str] = []
    if units < 3.0:
        missing.append("units<3")
    if confidence not in (tx.CONFIDENCE_MEDIUM, tx.CONFIDENCE_HIGH):
        missing.append("confidence-low")
    if attempts < MIN_ATTEMPTS_PROFICIENT:
        missing.append("volume<5")
    if puzzles < MIN_PUZZLES_PROFICIENT:
        missing.append("puzzles<2")
    if days < MIN_DAYS_PROFICIENT:
        missing.append("spread<2d")
    if max_difficulty is None or max_difficulty < MIN_DIFFICULTY_PROFICIENT:
        missing.append("difficulty<2")
    if clean < MIN_CLEAN_PROFICIENT:
        missing.append("clean<3")
    if not recent_ok:
        missing.append("recent-unclean")
    if not fresh:
        missing.append("stale")
    return missing


def _missing_mastered(
    *,
    units: float,
    confidence: str,
    attempts: int,
    puzzles: int,
    days: int,
    difficulties: int,
    max_difficulty: int | None,
    clean: int,
    recent_ok: bool,
    span_days: int | None,
    fresh: bool,
) -> list[str]:
    missing: list[str] = []
    if units < 3.0:
        missing.append("units<3")
    if confidence != tx.CONFIDENCE_HIGH:
        missing.append("confidence-not-high")
    if attempts < MIN_ATTEMPTS_MASTERED:
        missing.append("volume<8")
    if puzzles < MIN_PUZZLES_MASTERED:
        missing.append("puzzles<3")
    if days < MIN_DAYS_MASTERED:
        missing.append("spread<3d")
    if difficulties < MIN_DIFFICULTIES_MASTERED:
        missing.append("difficulty-diversity<2")
    if max_difficulty is None or max_difficulty < MIN_DIFFICULTY_MASTERED:
        missing.append("difficulty<3")
    if clean < MIN_CLEAN_MASTERED:
        missing.append("clean<5")
    if not recent_ok:
        missing.append("recent-unclean")
    if span_days is None or span_days < MIN_SPAN_DAYS_MASTERED:
        missing.append("retention<7d")
    if not fresh:
        missing.append("stale")
    return missing


def evaluate_state(state: Any, rows: Sequence[Any], *, reference: datetime | None = None) -> dict[str, SkillMastery]:
    """Mastery for every canonical skill from one skill state + history."""
    levels = getattr(state, "skills", {})
    out: dict[str, SkillMastery] = {}
    for skill in tx.SKILLS:
        out[skill] = evaluate_skill(skill, levels[skill], rows, reference=reference)
    return out


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


def mastery_for_user(
    db: Session, user_id: int, *, now: datetime | None = None
) -> dict[str, SkillMastery]:
    """Read-only mastery for one account. No flush, no commit."""
    rows = _rows_for_owner(db, user_id=user_id, guest_session_id=None)
    state = skill_state.aggregate(rows)
    return evaluate_state(state, rows, reference=now)


def mastery_for_guest(
    db: Session, guest_session_id: int, *, now: datetime | None = None
) -> dict[str, SkillMastery]:
    """Read-only mastery for one guest session. No flush, no commit."""
    rows = _rows_for_owner(db, user_id=None, guest_session_id=guest_session_id)
    state = skill_state.aggregate(rows)
    return evaluate_state(state, rows, reference=now)
