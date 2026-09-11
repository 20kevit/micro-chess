"""Phase 4 player rating engine: per-exercise, server-authoritative ratings.

Architecture (deliberately replaceable):

```text
Training Attempt
      ↓
is_rating_eligible  (server decides rated vs practice)
      ↓
calculate_update    (pure math, no DB / no HTTP)
      ↓
apply_rated_attempt (application service: rating row + event, one txn)
      ↓
PlayerRating (mutable current state) + RatingEvent (immutable history)
```

Rating algorithm (simple, deterministic, documented):

* Elo-style expected score against the puzzle's own rating
  (``Puzzle.initial_rating`` is the opponent): ``E = 1 / (1 + 10^((opp -
  rating) / 400))``. Beating a harder puzzle moves the rating more.
* Actual score from the validated server-side result: correct = 1.0,
  partial = 0.5, wrong = 0.0.
* ``delta = K * (score - expected)`` with ``K = 32`` while provisional
  and ``K = 16`` once established. Deltas round to 2 decimals.
* Ratings clamp to [100, 3000]; the stored delta is the clamped
  difference so ``after = before + delta`` always holds exactly.
* Uncertainty (RD) decays multiplicatively per rated attempt
  (``* 0.97``, floored at 50) — an explicit placeholder until a real
  Glicko/Glicko-2 implementation uses the stored deviation properly.
  Glicko-2 volatility and period processing are intentionally deferred.

Initial state (configured by this implementation, as RATINGS.md permits —
no canonical numeric value is specified anywhere, so these live here as
the single documented source):

* ``INITIAL_RATING = 1200`` (matches the ``Puzzle.initial_rating``
  default and the seeded puzzle scale, roughly 650–2100).
* ``INITIAL_RD = 350`` (Glicko new-player scale).
* ``PROVISIONAL_THRESHOLD = 10`` rated attempts.

Eligibility (server-decided, never trusted from the client):

* mode must be rated, the attempt must belong to an authenticated user
  (guests never rate), and the validated result must be one of
  correct/partial/wrong. Terminal client states (timeout/skipped/
  abandoned) never rate.

This module never commits: ``apply_rated_attempt`` flushes so the caller
(``progress.service.submit_attempt``) commits attempt + rating + event
atomically in one transaction.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.rating_engine.models import PlayerRating, RatingEvent
from app.modules.rule_engine.base import AttemptMode, AttemptResult

# --- configuration (single documented source; see module docstring) --------

INITIAL_RATING = 1200.0
INITIAL_RD = 350.0
PROVISIONAL_THRESHOLD = 10
K_PROVISIONAL = 32.0
K_ESTABLISHED = 16.0
RATING_MIN = 100.0
RATING_MAX = 3000.0
RD_MIN = 50.0
RD_DECAY_PER_ATTEMPT = 0.97

REASON_ATTEMPT = "attempt"

# Validated results that may move a rating. Terminal client-reported
# states (timeout/skipped/abandoned) are recorded in history but never
# rated; the server decides this, not the client.
RATED_RESULTS = frozenset(
    {AttemptResult.CORRECT.value, AttemptResult.PARTIAL.value, AttemptResult.WRONG.value}
)

_SCORE_FOR_RESULT = {
    AttemptResult.CORRECT.value: 1.0,
    AttemptResult.PARTIAL.value: 0.5,
    AttemptResult.WRONG.value: 0.0,
}


@dataclass(frozen=True)
class RatingUpdate:
    """Deterministic result of the pure rating calculation."""

    rating_before: float
    rating_delta: float
    rating_after: float
    rd_before: float
    rd_after: float
    games_before: int
    games_after: int
    provisional_after: bool


def score_for_result(result: str) -> float:
    """Authoritative actual score for a validated result string."""
    try:
        return _SCORE_FOR_RESULT[result]
    except KeyError:
        raise ValueError("result_not_ratable") from None


def is_rating_eligible(*, mode: AttemptMode, user_id: int | None, result: str) -> bool:
    """Server-side rated/unrated decision. Client flags are never trusted.

    Only an authenticated user's validated correct/partial/wrong attempt
    submitted in rated mode is eligible. Everything else (practice mode,
    guests, terminal states) is recorded as history but never rates.
    """
    return mode == AttemptMode.RATED and user_id is not None and result in RATED_RESULTS


def calculate_update(
    *,
    rating_before: float,
    rd_before: float,
    games_before: int,
    score: float,
    opponent_rating: float,
) -> RatingUpdate:
    """Pure rating math: no DB, no HTTP, no randomness. Fully deterministic."""
    provisional = games_before < PROVISIONAL_THRESHOLD
    k = K_PROVISIONAL if provisional else K_ESTABLISHED
    expected = 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating_before) / 400.0))
    raw_after = rating_before + k * (score - expected)
    clamped_after = min(RATING_MAX, max(RATING_MIN, raw_after))
    delta = round(clamped_after - rating_before, 2)
    after = round(rating_before + delta, 2)
    rd_after = round(max(RD_MIN, rd_before * RD_DECAY_PER_ATTEMPT), 2)
    games_after = games_before + 1
    return RatingUpdate(
        rating_before=round(rating_before, 2),
        rating_delta=delta,
        rating_after=after,
        rd_before=round(rd_before, 2),
        rd_after=rd_after,
        games_before=games_before,
        games_after=games_after,
        provisional_after=games_after < PROVISIONAL_THRESHOLD,
    )


# --- application service (persistence; still no HTTP) ------------------------


def get_rating(db: Session, user_id: int, exercise_slug: str) -> PlayerRating | None:
    """Current rating row, or None when the player has no rated attempts yet."""
    return (
        db.query(PlayerRating)
        .filter(
            PlayerRating.user_id == user_id,
            PlayerRating.exercise_slug == exercise_slug,
        )
        .first()
    )


def list_ratings(db: Session, user_id: int) -> list[PlayerRating]:
    """All of one player's per-exercise ratings, ordered by exercise."""
    return (
        db.query(PlayerRating)
        .filter(PlayerRating.user_id == user_id)
        .order_by(PlayerRating.exercise_slug)
        .all()
    )


def list_history(
    db: Session,
    user_id: int,
    exercise_slug: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> list[RatingEvent]:
    """Immutable rating events for one player + exercise, newest first."""
    return (
        db.query(RatingEvent)
        .filter(
            RatingEvent.user_id == user_id,
            RatingEvent.exercise_slug == exercise_slug,
        )
        .order_by(RatingEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def find_event_for_attempt(db: Session, attempt_id: int) -> RatingEvent | None:
    """Existing rating event for an attempt, if it was already processed."""
    return db.query(RatingEvent).filter(RatingEvent.attempt_id == attempt_id).first()


def apply_rated_attempt(
    db: Session,
    *,
    user_id: int,
    exercise_slug: str,
    attempt,
    result: str,
    puzzle_rating: float,
) -> tuple[PlayerRating, RatingEvent]:
    """Apply one validated rated attempt to the player's exercise rating.

    Idempotent: when an event already exists for ``attempt.id`` the stored
    (rating, event) pair is returned unchanged — reprocessing can never
    double-update the rating. Creates the player's rating row at the
    initial state on the first rated attempt. Also stamps the attempt's
    own ``rating_before``/``rating_delta``/``rating_after`` snapshot so
    attempt, rating, and event stay consistent.

    Flushes but never commits: the caller owns the transaction boundary.
    """
    existing = find_event_for_attempt(db, attempt.id)
    if existing is not None:
        rating = get_rating(db, user_id, exercise_slug)
        assert rating is not None  # event implies its rating row exists
        return rating, existing

    rating = get_rating(db, user_id, exercise_slug)
    if rating is None:
        rating = PlayerRating(
            user_id=user_id,
            exercise_slug=exercise_slug,
            rating=INITIAL_RATING,
            rating_deviation=INITIAL_RD,
            is_provisional=True,
            games_count=0,
        )
        db.add(rating)
        db.flush()

    update = calculate_update(
        rating_before=rating.rating,
        rd_before=rating.rating_deviation,
        games_before=rating.games_count,
        score=score_for_result(result),
        opponent_rating=puzzle_rating,
    )
    rating.rating = update.rating_after
    rating.rating_deviation = update.rd_after
    rating.games_count = update.games_after
    rating.is_provisional = update.provisional_after

    attempt.rating_before = update.rating_before
    attempt.rating_delta = update.rating_delta
    attempt.rating_after = update.rating_after

    event = RatingEvent(
        user_id=user_id,
        exercise_slug=exercise_slug,
        attempt_id=attempt.id,
        rating_before=update.rating_before,
        rating_delta=update.rating_delta,
        rating_after=update.rating_after,
        rating_deviation_before=update.rd_before,
        rating_deviation_after=update.rd_after,
        reason=REASON_ATTEMPT,
    )
    db.add(event)
    db.flush()
    return rating, event
