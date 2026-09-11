"""Phase 10 adaptive training: deterministic, explainable content selection.

Conceptual pipeline (see ``docs/platform/phases/PHASE_10_ADAPTIVE_TRAINING.md``)::

    Authoritative player state (ratings, attempts, response time)
        + authoritative content state (lifecycle, eligibility, difficulty)
        + observed difficulty (Phase 8 derived signal)
        -> eligibility filter (server-side, lifecycle-respecting)
        -> learner-signal classification (one machine-readable reason)
        -> difficulty-targeted ranking (deterministic; explicit seed only)
        -> next training item + persisted recommendation row

Rules enforced here:

* Selection is read-only over authoritative state: this module never
  creates attempts, never touches ratings/XP/streaks/achievements, never
  rewrites puzzle difficulty, and never recomputes observed difficulty.
  The only writes are rows in the module-owned
  ``adaptive_recommendations`` table (the Phase 10 feedback loop).
* Exercise scope is strict: a scoped request only ever returns content
  from that exercise. Cross-exercise choice happens only in the
  ``overview`` (adaptive exercise selection), never inside ``next``.
* Content eligibility mirrors the Phase 07 player-visibility rule
  (published + not archived) plus the Phase 06 exercise-availability
  rule (disabled exercises yield nothing; unknown exercises 404).
* Difficulty matching is ability-relative: the learner's current
  exercise rating (or the default for unrated learners) selects a
  target, and candidates rank by distance to that target. Content
  difficulty (``Puzzle.initial_rating``) and observed difficulty
  (platform accuracy) are reported side by side, never confused.
* No global randomness: ties/shortlists break by puzzle id by default;
  an explicit caller ``seed`` picks reproducibly among the top-ranked
  shortlist via ``random.Random(seed)`` (injectable for tests).
* Constants below are the single documented source for the policy
  knobs (same precedent as the Phase 04 rating constants and Phase 05
  XP rules: the canonical docs permit implementation configuration,
  so the numbers live here, documented and tested, not scattered).

Reason vocabulary (a superset of the Phase 10 examples; the spec lists
examples, and ``COLD_START``/``APPROPRIATE_DIFFICULTY`` cover the
baseline/stable cases the examples leave unnamed):

* ``WEAK_EXERCISE`` — low overall accuracy needs targeted practice.
* ``RECENT_FAILURES`` — recent repeated failures need remediation
  (easier content).
* ``READY_FOR_HARDER`` — strong, improving performance earns a
  controlled difficulty increase.
* ``LOW_RECENT_ACTIVITY`` — stale exercise needs re-engagement.
* ``MASTERY_REVIEW`` — strong but stale exercise needs review.
  (Documented definition: accuracy >= ``STRONG_ACCURACY`` with at
  least ``MIN_SIGNAL_ATTEMPTS`` attempts and no practice for at
  least ``STALE_DAYS``.)
* ``APPROPRIATE_DIFFICULTY`` — stable skill, keep appropriate progression.
* ``COLD_START`` — no usable evidence yet; documented baseline selection.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.adaptive.models import (
    RECOMMENDATION_TRANSITIONS,
    STATUS_SHOWN,
    AdaptiveRecommendation,
)
from app.modules.analytics.service import MIN_OBSERVED_ATTEMPTS, observed_difficulty
from app.modules.exercises import registry
from app.modules.exercises.models import Exercise
from app.modules.player.service import is_known_exercise
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.models import PlayerRating, RatingEvent
from app.modules.rating_engine.service import INITIAL_RATING, RATING_MAX, RATING_MIN

# --- policy configuration (single documented source; see module docstring) ---

# Learner-signal windows and thresholds.
RECENT_WINDOW = 10  # attempts forming the "recent" signal per exercise
RECENCY_EXCLUSION = 20  # own attempts whose puzzles `next` avoids re-serving
MIN_SIGNAL_ATTEMPTS = 5  # attempts before accuracy labels mean anything
WEAK_ACCURACY = 0.5  # overall accuracy below this => WEAK_EXERCISE
STRONG_ACCURACY = 0.8  # recent accuracy at/above this => strong performance
RECENT_FAILURES_TRIGGER = 3  # non-correct in RECENT_WINDOW => remediation
STALE_DAYS = 7  # no practice for this long => stale

# Difficulty matching.
DIFFICULTY_BAND = 250.0  # |initial - ability| within this => suitable
REMEDIATION_OFFSET = -200.0  # RECENT_FAILURES aims below ability
CHALLENGE_OFFSET = 150.0  # READY_FOR_HARDER aims modestly above ability
SHORTLIST_SIZE = 5  # seeded selection picks reproducibly among the top-N

# Candidate-set bound (database-side limit before Python ranking).
MAX_CANDIDATES = 500

# Machine-readable reasons (superset of the Phase 10 examples).
REASON_WEAK_EXERCISE = "WEAK_EXERCISE"
REASON_RECENT_FAILURES = "RECENT_FAILURES"
REASON_READY_FOR_HARDER = "READY_FOR_HARDER"
REASON_LOW_ACTIVITY = "LOW_RECENT_ACTIVITY"
REASON_MASTERY_REVIEW = "MASTERY_REVIEW"
REASON_APPROPRIATE = "APPROPRIATE_DIFFICULTY"
REASON_COLD_START = "COLD_START"

REASONS = frozenset(
    {
        REASON_WEAK_EXERCISE,
        REASON_RECENT_FAILURES,
        REASON_READY_FOR_HARDER,
        REASON_LOW_ACTIVITY,
        REASON_MASTERY_REVIEW,
        REASON_APPROPRIATE,
        REASON_COLD_START,
    }
)

# Overview recommendation priority (highest first): struggling learners
# outrank re-engagement, which outranks enrichment.
REASON_PRIORITY = (
    REASON_RECENT_FAILURES,
    REASON_WEAK_EXERCISE,
    REASON_LOW_ACTIVITY,
    REASON_MASTERY_REVIEW,
    REASON_READY_FOR_HARDER,
    REASON_APPROPRIATE,
    REASON_COLD_START,
)

OUTCOME_RESULTS = frozenset({"correct", "partial", "wrong", "timeout", "skipped", "abandoned"})


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class ExerciseSignals:
    """Derived learner signals for one player + exercise (read-only view)."""

    exercise: str
    attempts: int
    accuracy: float
    recent_accuracy: float | None
    recent_failures: int
    repeated_mistakes: int
    avg_response_ms: float | None
    days_since_last: int | None
    rating: float | None
    provisional: bool | None
    games: int
    rating_trend: float
    reason: str


@dataclass(frozen=True)
class RankedCandidate:
    puzzle_id: int
    distance: float
    observed_difficulty: str


def ability_for(db: Session, user_id: int, exercise_slug: str) -> tuple[float, bool | None, int]:
    """Learner ability for an exercise: current rating, else the default.

    Returns ``(ability, provisional, games)``. Unrated learners use
    ``INITIAL_RATING`` (the same documented default the rating engine
    starts from), so cold-start selection is well-defined.
    """
    row: PlayerRating | None = (
        db.query(PlayerRating)
        .filter(PlayerRating.user_id == user_id, PlayerRating.exercise_slug == exercise_slug)
        .first()
    )
    if row is None:
        return INITIAL_RATING, None, 0
    return float(row.rating), bool(row.is_provisional), int(row.games_count)


def exercise_signals(db: Session, user_id: int, exercise_slug: str) -> ExerciseSignals:
    """Derive learner signals for one player + exercise from authoritative data.

    Read-only: aggregate queries over ``attempts`` / ``rating_events`` /
    ``player_ratings``. Bounded (one aggregate query + one capped recent
    query + one small rating query), no N+1.
    """
    now = _utcnow_naive()
    counts = (
        db.query(Attempt.result, func.count(Attempt.id))
        .filter(Attempt.user_id == user_id, Attempt.exercise_slug == exercise_slug)
        .group_by(Attempt.result)
        .all()
    )
    total = sum(n for _r, n in counts)
    correct = sum(n for r, n in counts if r == "correct")
    accuracy = (correct / total) if total else 0.0

    recent = (
        db.query(Attempt.result, Attempt.puzzle_id, Attempt.created_at, Attempt.duration_ms)
        .filter(Attempt.user_id == user_id, Attempt.exercise_slug == exercise_slug)
        .order_by(Attempt.id.desc())
        .limit(RECENT_WINDOW)
        .all()
    )
    recent_accuracy: float | None = None
    recent_failures = 0
    repeated_mistakes = 0
    days_since_last: int | None = None
    if recent:
        recent_accuracy = sum(1 for r, _p, _at, _d in recent if r == "correct") / len(recent)
        recent_failures = sum(1 for r, _p, _at, _d in recent if r != "correct")
        wrong_by_puzzle: dict[int, int] = {}
        for result, puzzle_id, _at, _dur in recent:
            if result == "wrong":
                wrong_by_puzzle[puzzle_id] = wrong_by_puzzle.get(puzzle_id, 0) + 1
        repeated_mistakes = sum(1 for n in wrong_by_puzzle.values() if n >= 2)
        latest = max((at for _r, _p, at, _d in recent if at is not None), default=None)
        if latest is not None:
            days_since_last = max(0, (now - latest).days)

    avg_response: float | None = (
        db.query(func.avg(Attempt.duration_ms))
        .filter(
            Attempt.user_id == user_id,
            Attempt.exercise_slug == exercise_slug,
            Attempt.duration_ms.is_not(None),
        )
        .scalar()
    )
    avg_response_ms = float(avg_response) if avg_response is not None else None

    ability, provisional, games = ability_for(db, user_id, exercise_slug)
    trend_rows = (
        db.query(RatingEvent.rating_delta)
        .filter(RatingEvent.user_id == user_id, RatingEvent.exercise_slug == exercise_slug)
        .order_by(RatingEvent.id.desc())
        .limit(RECENT_WINDOW // 2)
        .all()
    )
    trend = round(sum(d for (d,) in trend_rows), 2)

    reason = classify_reason(
        attempts=total,
        accuracy=accuracy,
        recent_accuracy=recent_accuracy,
        recent_failures=recent_failures,
        days_since_last=days_since_last,
        rating_trend=trend,
        recent_count=len(recent),
    )
    return ExerciseSignals(
        exercise=exercise_slug,
        attempts=total,
        accuracy=accuracy,
        recent_accuracy=recent_accuracy,
        recent_failures=recent_failures,
        repeated_mistakes=repeated_mistakes,
        avg_response_ms=avg_response_ms,
        days_since_last=days_since_last,
        rating=ability if games else None,
        provisional=provisional,
        games=games,
        rating_trend=trend,
        reason=reason,
    )


def classify_reason(
    *,
    attempts: int,
    accuracy: float,
    recent_accuracy: float | None,
    recent_failures: int,
    days_since_last: int | None,
    rating_trend: float,
    recent_count: int,
) -> str:
    """Pure classification of learner signals into one reason.

    Priority order is part of the contract (struggling first):
    RECENT_FAILURES > WEAK_EXERCISE > LOW_RECENT_ACTIVITY >
    MASTERY_REVIEW > READY_FOR_HARDER > APPROPRIATE_DIFFICULTY,
    with COLD_START when there is no evidence at all.
    """
    if attempts == 0:
        return REASON_COLD_START
    stale = days_since_last is not None and days_since_last >= STALE_DAYS
    if recent_count >= MIN_SIGNAL_ATTEMPTS and recent_failures >= RECENT_FAILURES_TRIGGER:
        return REASON_RECENT_FAILURES
    if attempts >= MIN_SIGNAL_ATTEMPTS and accuracy < WEAK_ACCURACY:
        return REASON_WEAK_EXERCISE
    if stale and attempts > 0:
        if attempts >= MIN_SIGNAL_ATTEMPTS and accuracy >= STRONG_ACCURACY:
            return REASON_MASTERY_REVIEW
        return REASON_LOW_ACTIVITY
    if (
        recent_accuracy is not None
        and recent_count >= MIN_SIGNAL_ATTEMPTS
        and recent_accuracy >= STRONG_ACCURACY
        and recent_failures < 2
        and rating_trend > 0
    ):
        return REASON_READY_FOR_HARDER
    return REASON_APPROPRIATE


def target_for_reason(reason: str, ability: float) -> float:
    """Difficulty target for a reason: remediation aims below ability,
    enrichment modestly above, everything else at ability. Clamped to the
    canonical rating bounds (never an excessive difficulty jump)."""
    if reason == REASON_RECENT_FAILURES:
        target = ability + REMEDIATION_OFFSET
    elif reason == REASON_READY_FOR_HARDER:
        target = ability + CHALLENGE_OFFSET
    else:
        target = ability
    return min(RATING_MAX, max(RATING_MIN, target))


def _eligible_puzzles(db: Session, exercise_slug: str) -> list[Puzzle]:
    """Player-visible puzzles for one exercise (database-side filter).

    Mirrors the Phase 07 visibility projection (published + not
    archived). Disabled exercises yield nothing (Phase 06
    availability); exercises without a catalog row stay selectable so
    pre-admin content keeps working (same precedent as attempt
    submission).
    """
    exercise = db.get(Exercise, exercise_slug)
    if exercise is not None and not exercise.is_active:
        return []
    return (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == exercise_slug,
            Puzzle.is_published == True,  # noqa: E712
            Puzzle.is_archived == False,  # noqa: E712
        )
        .order_by(Puzzle.id)
        .limit(MAX_CANDIDATES)
        .all()
    )


def _observed_by_puzzle(db: Session, puzzle_ids: list[int]) -> dict[int, str]:
    """Observed difficulty per candidate (one aggregate query, never persisted)."""
    if not puzzle_ids:
        return {}
    rows = (
        db.query(Attempt.puzzle_id, Attempt.result, func.count(Attempt.id))
        .filter(Attempt.puzzle_id.in_(puzzle_ids), Attempt.user_id.is_not(None))
        .group_by(Attempt.puzzle_id, Attempt.result)
        .all()
    )
    totals: dict[int, int] = {}
    corrects: dict[int, int] = {}
    for puzzle_id, result, count in rows:
        totals[puzzle_id] = totals.get(puzzle_id, 0) + int(count)
        if result == "correct":
            corrects[puzzle_id] = corrects.get(puzzle_id, 0) + int(count)
    labels: dict[int, str] = {}
    for puzzle_id in puzzle_ids:
        attempts = totals.get(puzzle_id, 0)
        accuracy = (corrects.get(puzzle_id, 0) / attempts) if attempts else 0.0
        labels[puzzle_id] = observed_difficulty(accuracy, attempts)
    return labels


def _recent_puzzle_ids(db: Session, user_id: int, exercise_slug: str, limit: int) -> list[int]:
    rows = (
        db.query(Attempt.puzzle_id)
        .filter(Attempt.user_id == user_id, Attempt.exercise_slug == exercise_slug)
        .order_by(Attempt.id.desc())
        .limit(limit)
        .all()
    )
    return [puzzle_id for (puzzle_id,) in rows]


def rank_candidates(
    candidates: list[Puzzle],
    *,
    target: float,
    observed: dict[int, str] | None = None,
    exclude_ids: set[int] | None = None,
) -> list[RankedCandidate]:
    """Pure ranking: by distance to target, ties broken by puzzle id.

    No randomness here — reproducibility comes from this stable order;
    the optional caller seed only selects within the top shortlist.
    """
    excluded = exclude_ids or set()
    ranked = [
        RankedCandidate(
            puzzle_id=puzzle.id,
            distance=abs(float(puzzle.initial_rating or INITIAL_RATING) - target),
            observed_difficulty=(observed or {}).get(puzzle.id, "insufficient_data"),
        )
        for puzzle in candidates
        if puzzle.id not in excluded
    ]
    ranked.sort(key=lambda c: (c.distance, c.puzzle_id))
    return ranked


def pick_candidate(
    ranked: list[RankedCandidate], *, seed: int | None = None, rng: random.Random | None = None
) -> RankedCandidate | None:
    """Select one candidate: top-ranked by default; with an explicit seed,
    reproducibly one of the top-ranked shortlist (never global random)."""
    if not ranked:
        return None
    shortlist = ranked[:SHORTLIST_SIZE]
    if seed is None:
        return shortlist[0]
    chooser = rng if rng is not None else random.Random(seed)
    return shortlist[chooser.randrange(len(shortlist))]


def _known_scopes(db: Session) -> set[str]:
    scopes = set(registry.registered_slugs())
    for (slug,) in db.query(Exercise.slug).all():
        scopes.add(slug)
    return scopes


def overview(db: Session, user_id: int) -> dict:
    """Adaptive exercise selection: signals per exercise + one recommendation.

    Covers every known exercise that has evidence (attempts or a rating)
    or published content worth starting. The recommended exercise is the
    alphabetically-first holder of the highest-priority reason, so the
    choice is deterministic. Cold-start learners (no attempts anywhere)
    get the baseline: the first content-bearing active exercise.
    """
    scopes = sorted(_known_scopes(db))
    signals = [exercise_signals(db, user_id, slug) for slug in scopes]
    evidence = [s for s in signals if s.attempts > 0 or s.games > 0]
    if not evidence:
        # Baseline: first active scope with published content (cold start).
        baseline: str | None = None
        for slug in scopes:
            exercise = db.get(Exercise, slug)
            if exercise is not None and not exercise.is_active:
                continue
            has_content = (
                db.query(Puzzle.id)
                .filter(
                    Puzzle.exercise_slug == slug,
                    Puzzle.is_published == True,  # noqa: E712
                    Puzzle.is_archived == False,  # noqa: E712
                )
                .first()
                is not None
            )
            if has_content:
                baseline = slug
                break
        rows = [s for s in signals if baseline is not None and s.exercise == baseline]
        return {"exercises": rows, "recommended_exercise": baseline, "reason": REASON_COLD_START if baseline else None}
    order = {reason: index for index, reason in enumerate(REASON_PRIORITY)}
    best = min(evidence, key=lambda s: (order[s.reason], s.exercise))
    return {
        "exercises": evidence,
        "recommended_exercise": best.exercise,
        "reason": best.reason,
    }


def next_for_exercise(
    db: Session,
    user_id: int,
    exercise_slug: str,
    *,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Select the next training puzzle for one exercise and record it.

    Raises ``ValueError`` with ``exercise_not_found`` (unknown slug),
    ``exercise_not_available`` (disabled exercise), or
    ``no_eligible_content`` (nothing selectable). Selection itself is
    read-only; the only write is the module-owned ``shown``
    recommendation row (attempts/ratings/XP untouched).
    """
    if not is_known_exercise(db, exercise_slug):
        raise ValueError("exercise_not_found")
    candidates = _eligible_puzzles(db, exercise_slug)
    if not candidates:
        exercise = db.get(Exercise, exercise_slug)
        if exercise is not None and not exercise.is_active:
            raise ValueError("exercise_not_available")
        raise ValueError("no_eligible_content")

    signals = exercise_signals(db, user_id, exercise_slug)
    ability, _provisional, _games = ability_for(db, user_id, exercise_slug)
    target = target_for_reason(signals.reason, ability)
    observed = _observed_by_puzzle(db, [p.id for p in candidates])

    recent_ids = set(_recent_puzzle_ids(db, user_id, exercise_slug, RECENCY_EXCLUSION))
    ranked = rank_candidates(candidates, target=target, observed=observed, exclude_ids=recent_ids)
    fallback = False
    if not ranked:
        # Documented fallback: repetition avoidance relaxes rather than
        # stranding the learner; lifecycle rules are never relaxed.
        ranked = rank_candidates(candidates, target=target, observed=observed)
        fallback = True
    picked = pick_candidate(ranked, seed=seed, rng=rng)
    assert picked is not None  # candidates non-empty => ranked non-empty
    puzzle = next(p for p in candidates if p.id == picked.puzzle_id)

    row = AdaptiveRecommendation(
        user_id=user_id,
        exercise_slug=exercise_slug,
        puzzle_id=puzzle.id,
        reason=signals.reason,
        ability_rating=ability,
        target_rating=target,
        seed=seed,
        status=STATUS_SHOWN,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "puzzle": puzzle,
        "reason": signals.reason,
        "ability_rating": ability,
        "target_rating": target,
        "observed_difficulty": picked.observed_difficulty,
        "recommendation_id": row.id,
        "fallback": fallback,
    }


def record_outcome(
    db: Session, user_id: int, recommendation_id: int, *, status: str, result: str | None = None
) -> AdaptiveRecommendation | None:
    """Advance one owned recommendation through its lifecycle.

    Returns None when the row is missing or belongs to another learner
    (callers map both to 404 so recommendations are not enumerable).
    Raises ``ValueError`` (``invalid_transition`` / ``invalid_status`` /
    ``invalid_result``) for illegal moves.
    """
    row: AdaptiveRecommendation | None = db.get(AdaptiveRecommendation, recommendation_id)
    if row is None or row.user_id != user_id:
        return None
    clean_status = str(status or "").strip().lower()
    if clean_status not in RECOMMENDATION_TRANSITIONS.get(row.status, frozenset()):
        raise ValueError("invalid_transition" if clean_status in (
            "shown", "accepted", "completed", "skipped",
        ) else "invalid_status")
    clean_result: str | None = None
    if result is not None:
        clean_result = str(result).strip().lower()
        if clean_result not in OUTCOME_RESULTS:
            raise ValueError("invalid_result")
    row.status = clean_status
    if clean_result is not None:
        row.result = clean_result
    db.commit()
    db.refresh(row)
    return row


def list_history(
    db: Session, user_id: int, *, page: int = 1, page_size: int = 50
) -> list[AdaptiveRecommendation]:
    """Own recommendation history, newest first (feedback-loop inspection)."""
    return (
        db.query(AdaptiveRecommendation)
        .filter(AdaptiveRecommendation.user_id == user_id)
        .order_by(AdaptiveRecommendation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
