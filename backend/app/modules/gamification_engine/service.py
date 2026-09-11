"""Phase 5 gamification engine: XP, levels, streaks, achievements.

Architecture (mirrors the rating engine on purpose):

```text
Training Attempt (authoritative, server-validated)
      ↓
is_xp_eligible      (server decides; mode-independent, guests excluded)
      ↓
xp_for_result       (pure math, no DB / no HTTP)
level_for_total     (pure math, no DB / no HTTP)
      ↓
apply_attempt       (application service: XP event + state + streak
                     + achievements, one transaction with the attempt)
      ↓
XpEvent (immutable history) + PlayerGamificationState +
PlayerStreak (mutable projections) + PlayerAchievement (unlocks)
```

Configuration (single documented source — GAMIFICATION.md intentionally
leaves numeric rules configurable instead of fixing them, so these live
here exactly like the rating engine's documented configuration):

* ``XP_CORRECT = 10``, ``XP_PARTIAL = 5``, ``XP_WRONG = 2``: every
  validated correct/partial/wrong attempt by an authenticated user earns
  a small fixed amount, in both practice and rated modes (gamification
  eligibility is deliberately separate from Phase 4 rating eligibility).
  Terminal client states (timeout/skipped/abandoned) never earn XP, and
  guests never earn persistent XP.
* ``LEVEL_XP_STEP = 100``: ``level = total_xp // 100 + 1``. Level 1
  covers 0–99 XP, level 2 covers 100–199 XP, and so on.
* Streak days use UTC dates derived from the server timestamp (the
  repository-wide timestamp convention): one qualifying attempt marks
  the day active; consecutive days extend, a repeated day is a no-op,
  and a gap resets to 1.

Achievements (Phase 5 foundation catalog — small, deterministic,
one-time; definitions in code, unlocks in the database):

* ``first_steps`` — first qualifying attempt.
* ``steady_10`` — 10 qualifying attempts.
* ``xp_100`` — 100 total XP.
* ``streak_3`` — longest streak reaches 3 days.

This module never commits: ``apply_attempt`` flushes so the caller
(``progress.service.submit_attempt``) commits attempt + XP + streak +
achievements atomically in one transaction.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.modules.gamification_engine.models import (
    PlayerAchievement,
    PlayerGamificationState,
    PlayerStreak,
    XpEvent,
)

# --- configuration (single documented source; see module docstring) --------

XP_CORRECT = 10
XP_PARTIAL = 5
XP_WRONG = 2

LEVEL_XP_STEP = 100

REASON_ATTEMPT = "attempt"

# Validated results that earn XP. Terminal client-reported states
# (timeout/skipped/abandoned) are recorded in history but never rewarded;
# the server decides this, not the client.
XP_RESULTS = frozenset({"correct", "partial", "wrong"})

_XP_FOR_RESULT = {
    "correct": XP_CORRECT,
    "partial": XP_PARTIAL,
    "wrong": XP_WRONG,
}


@dataclass(frozen=True)
class AchievementDefinition:
    """One entry of the Phase 5 achievement catalog (code is the key)."""

    code: str


# Phase 5 foundation catalog. Codes are stable identifiers: unlock rows
# reference them and the frontend maps them to Persian text.
ACHIEVEMENTS: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(code="first_steps"),
    AchievementDefinition(code="steady_10"),
    AchievementDefinition(code="xp_100"),
    AchievementDefinition(code="streak_3"),
)

ACHIEVEMENT_CODES = frozenset(a.code for a in ACHIEVEMENTS)


# --- pure rules (no DB, no HTTP, deterministic) ------------------------------


def xp_for_result(result: str) -> int:
    """Authoritative XP amount for a validated result string."""
    try:
        return _XP_FOR_RESULT[result]
    except KeyError:
        raise ValueError("result_not_xp_eligible") from None


def is_xp_eligible(*, user_id: int | None, result: str) -> bool:
    """Server-side XP decision. Client flags are never trusted.

    Any authenticated user's validated correct/partial/wrong attempt is
    eligible, in both practice and rated modes. Guests, anonymous
    submissions, and terminal states never earn persistent XP.
    """
    return user_id is not None and result in XP_RESULTS


def level_for_total(total_xp: int) -> int:
    """Deterministic level derived from accumulated XP (1-based)."""
    if total_xp < 0:
        raise ValueError("xp_total_negative")
    return total_xp // LEVEL_XP_STEP + 1


def xp_progress_in_level(total_xp: int) -> tuple[int, int]:
    """(xp_into_current_level, xp_needed_for_next_level) for display."""
    if total_xp < 0:
        raise ValueError("xp_total_negative")
    into_level = total_xp % LEVEL_XP_STEP
    return into_level, LEVEL_XP_STEP


# --- application service (persistence; still no HTTP) ------------------------


def get_state(db: Session, user_id: int) -> PlayerGamificationState | None:
    """Current gamification state, or None before the first XP award."""
    return (
        db.query(PlayerGamificationState)
        .filter(PlayerGamificationState.user_id == user_id)
        .first()
    )


def get_or_create_state(db: Session, user_id: int) -> PlayerGamificationState:
    state = get_state(db, user_id)
    if state is None:
        state = PlayerGamificationState(user_id=user_id, total_xp=0, level=1)
        db.add(state)
        db.flush()
    return state


def find_event_for_attempt(db: Session, attempt_id: int) -> XpEvent | None:
    """Existing XP event for an attempt, if it was already processed."""
    return db.query(XpEvent).filter(XpEvent.attempt_id == attempt_id).first()


def get_streak(db: Session, user_id: int) -> PlayerStreak | None:
    return db.query(PlayerStreak).filter(PlayerStreak.user_id == user_id).first()


def get_or_create_streak(db: Session, user_id: int) -> PlayerStreak:
    streak = get_streak(db, user_id)
    if streak is None:
        streak = PlayerStreak(user_id=user_id, current_streak=0, longest_streak=0)
        db.add(streak)
        db.flush()
    return streak


def update_streak(db: Session, *, user_id: int, active_date: date) -> PlayerStreak:
    """Record qualifying activity on a UTC date. Idempotent per date.

    First activity starts the streak at 1; the next consecutive day
    extends it; repeated activity on the same day leaves it unchanged;
    a missed day (gap of 2+) resets it to 1. Never moves backwards.
    """
    streak = get_or_create_streak(db, user_id)
    last = streak.last_qualified_date
    if last == active_date:
        return streak
    if last is None:
        streak.current_streak = 1
    else:
        gap = (active_date - last).days
        if gap == 1:
            streak.current_streak += 1
        elif gap > 1:
            streak.current_streak = 1
        else:
            # Out-of-order (older) activity must not corrupt the streak.
            return streak
    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak
    streak.last_qualified_date = active_date
    db.flush()
    return streak


def qualifying_attempt_count(db: Session, user_id: int) -> int:
    """Number of XP-earning attempts (== number of XP events)."""
    return db.query(XpEvent).filter(XpEvent.user_id == user_id).count()


def list_unlocks(db: Session, user_id: int) -> list[PlayerAchievement]:
    return (
        db.query(PlayerAchievement)
        .filter(PlayerAchievement.user_id == user_id)
        .order_by(PlayerAchievement.id)
        .all()
    )


def evaluate_achievements(db: Session, *, user_id: int) -> list[PlayerAchievement]:
    """Unlock newly earned achievements. Deterministic and idempotent.

    Safe to run repeatedly: already-unlocked codes are skipped, and the
    unique (user_id, achievement_code) constraint backstops duplicates.
    Returns only the achievements unlocked by this call.
    """
    state = get_state(db, user_id)
    total_xp = state.total_xp if state else 0
    attempts = qualifying_attempt_count(db, user_id)
    streak = get_streak(db, user_id)
    longest = streak.longest_streak if streak else 0

    earned: set[str] = set()
    if attempts >= 1:
        earned.add("first_steps")
    if attempts >= 10:
        earned.add("steady_10")
    if total_xp >= 100:
        earned.add("xp_100")
    if longest >= 3:
        earned.add("streak_3")
    earned &= ACHIEVEMENT_CODES

    owned = {row.achievement_code for row in list_unlocks(db, user_id)}
    newly_unlocked: list[PlayerAchievement] = []
    for code in sorted(earned - owned):
        row = PlayerAchievement(user_id=user_id, achievement_code=code)
        db.add(row)
        newly_unlocked.append(row)
    if newly_unlocked:
        db.flush()
    return newly_unlocked


def apply_attempt(
    db: Session,
    *,
    user_id: int,
    attempt,
    result: str,
    active_date: date,
) -> XpEvent:
    """Apply one validated XP-eligible attempt to the player's state.

    Idempotent: when an event already exists for ``attempt.id`` the
    stored event is returned unchanged — reprocessing can never
    double-award XP, double-count the day, or duplicate unlocks. Also
    stamps the attempt's own ``xp_awarded`` snapshot so attempt, state,
    and event stay consistent.

    Flushes but never commits: the caller owns the transaction boundary.
    """
    existing = find_event_for_attempt(db, attempt.id)
    if existing is not None:
        return existing

    amount = xp_for_result(result)
    state = get_or_create_state(db, user_id)
    state.total_xp += amount
    state.level = level_for_total(state.total_xp)

    attempt.xp_awarded = amount

    event = XpEvent(
        user_id=user_id,
        amount=amount,
        reason=REASON_ATTEMPT,
        attempt_id=attempt.id,
        balance_after=state.total_xp,
    )
    db.add(event)
    db.flush()

    update_streak(db, user_id=user_id, active_date=active_date)
    evaluate_achievements(db, user_id=user_id)
    return event


def list_xp_history(
    db: Session,
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
) -> list[XpEvent]:
    """Immutable XP events for one player, newest first."""
    return (
        db.query(XpEvent)
        .filter(XpEvent.user_id == user_id)
        .order_by(XpEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
