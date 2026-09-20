"""Phase 8 analytics: read-only derived metrics over authoritative history.

Logical flow (no second source of truth)::

    attempts / rating_events / xp_events / streaks / content metadata
        -> analytics queries / aggregation (this module)
        -> derived metrics (plain dicts)
        -> API schemas -> player / admin UI

Rules enforced here:

* Read-only: this module never adds, commits, or mutates any row.
  Analytics requests must be reproducible from source records.
* Server-side UTC windows: ``resolve_window`` maps ``7d`` / ``30d`` /
  ``90d`` / ``all`` / ``custom`` to naive-UTC ``[start, end)`` bounds,
  matching the repository-wide UTC timestamp convention. Rolling windows
  are exact 24h multiples ending at ``now``; custom ranges use UTC
  calendar days (``date_from`` 00:00 inclusive to ``date_to`` + 1 day
  00:00 exclusive).
* Authenticated attempts only (``user_id IS NOT NULL``): guest attempts
  are temporary by design (see GAMIFICATION.md section 11) and enter
  analytics only after ``/guest/migrate`` transfers ownership, at which
  point they carry ``user_id`` like any other attempt.
* Accuracy denominator: ``correct / attempts`` over ALL attempts in
  scope (including terminal timeout/skipped/abandoned), consistent with
  the Phase 3 ``progress_summary`` contract. Partial/wrong/terminal
  counts are exposed separately so denominators stay auditable.
* Response time: ``avg`` / ``sum`` over attempts whose ``duration_ms``
  is not NULL; ``None``/``0`` when no timed attempts exist.
* Observed difficulty is derived per puzzle (``easy`` / ``medium`` /
  ``hard`` from accuracy, ``insufficient_data`` below the attempt
  threshold) and is never written back to ``Puzzle``. Adaptive
  difficulty belongs to Phase 10.
* No unified training-session table exists (speed sessions are
  exercise-scoped tables with no shared model), so there is deliberately
  no cross-exercise "session count" metric: ``active_days`` is the
  consistency signal. Formal session aggregation would require a new
  generic framework and is deferred.
* Mastery/leaderboards/goals have no source tables yet (Phase 5
  intentional deferrals) and are therefore not exposed here.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.adaptive.models import AdaptiveRecommendation
from app.modules.evidence.models import Evidence
from app.modules.exercises import registry
from app.modules.exercises.models import Exercise
from app.modules.gamification_engine.models import (
    PlayerGamificationState,
    PlayerStreak,
    XpEvent,
)
from app.modules.gamification_engine.service import level_for_total
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import Puzzle
from app.modules.rating_engine.models import PlayerRating, RatingEvent
from app.modules.users.models import User

VALID_PERIODS = ("7d", "30d", "90d", "all", "custom")
ROLLING_DAYS = {"7d": 7, "30d": 30, "90d": 90}

# Buckets stay daily for focused windows; longer spans aggregate weekly
# so responses stay bounded without a second query language.
DAILY_BUCKET_LIMIT_DAYS = 120

# Observed difficulty needs a minimum sample before the label means
# anything; below this the puzzle reports ``insufficient_data``.
MIN_OBSERVED_ATTEMPTS = 5

TERMINAL_RESULTS = frozenset({"timeout", "skipped", "abandoned"})


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class Window:
    """Resolved server-side UTC window: ``[start, end)``; ``start`` is None for all-time."""

    period: str
    start: datetime | None
    end: datetime
    days: int | None  # exact span for bounded windows; None for all-time


def resolve_window(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    now: datetime | None = None,
) -> Window:
    """Map a period request to UTC bounds. Raises ValueError on bad input."""
    current = now or _utcnow_naive()
    if period in ROLLING_DAYS:
        days = ROLLING_DAYS[period]
        return Window(period=period, start=current - timedelta(days=days), end=current, days=days)
    if period == "all":
        return Window(period=period, start=None, end=current, days=None)
    if period == "custom":
        if not date_from or not date_to:
            raise ValueError("date_range_required")
        try:
            from_day = date.fromisoformat(date_from.strip())
            to_day = date.fromisoformat(date_to.strip())
        except (ValueError, AttributeError):
            raise ValueError("invalid_date_range") from None
        if from_day > to_day:
            raise ValueError("invalid_date_range")
        start = datetime(from_day.year, from_day.month, from_day.day)
        end = datetime(to_day.year, to_day.month, to_day.day) + timedelta(days=1)
        return Window(period=period, start=start, end=end, days=(end - start).days)
    raise ValueError("invalid_period")


def _previous_window(window: Window) -> Window:
    """The equivalent-length period immediately before ``window``."""
    if window.start is None or not window.days:
        raise ValueError("comparison_requires_bounded_period")
    length = window.end - window.start
    return Window(
        period=window.period,
        start=window.start - length,
        end=window.start,
        days=window.days,
    )


# --- attempt rows ------------------------------------------------------------
# Column-light tuples (no full ORM objects, single query per request, no N+1).
# Tuple: (result, mode, exercise_slug, puzzle_id, user_id, created_at, duration_ms)


def _player_attempt_rows(
    db: Session, user_id: int, window: Window, exercise: str | None = None
) -> list[tuple]:
    q = (
        db.query(
            Attempt.result,
            Attempt.mode,
            Attempt.exercise_slug,
            Attempt.puzzle_id,
            Attempt.user_id,
            Attempt.created_at,
            Attempt.duration_ms,
        )
        .filter(Attempt.user_id == user_id)
        .filter(Attempt.created_at < window.end)
    )
    if window.start is not None:
        q = q.filter(Attempt.created_at >= window.start)
    if exercise:
        q = q.filter(Attempt.exercise_slug == exercise)
    return q.order_by(Attempt.id).all()


def _platform_attempt_rows(db: Session, window: Window) -> list[tuple]:
    q = (
        db.query(
            Attempt.result,
            Attempt.mode,
            Attempt.exercise_slug,
            Attempt.puzzle_id,
            Attempt.user_id,
            Attempt.created_at,
            Attempt.duration_ms,
        )
        .filter(Attempt.user_id.is_not(None))
        .filter(Attempt.created_at < window.end)
    )
    if window.start is not None:
        q = q.filter(Attempt.created_at >= window.start)
    return q.order_by(Attempt.id).all()


def _summarize(rows: list[tuple]) -> dict:
    """Aggregate attempt tuples. Denominator rules live in the module docstring."""
    attempts = len(rows)
    correct = sum(1 for r in rows if r[0] == "correct")
    partial = sum(1 for r in rows if r[0] == "partial")
    wrong = sum(1 for r in rows if r[0] == "wrong")
    terminal = sum(1 for r in rows if r[0] in TERMINAL_RESULTS)
    durations = [r[6] for r in rows if r[6] is not None]
    by_mode: dict[str, dict] = {}
    for result, mode, _slug, _pid, _uid, _at, _dur in rows:
        entry = by_mode.setdefault(mode, {"mode": mode, "attempts": 0, "correct": 0})
        entry["attempts"] += 1
        if result == "correct":
            entry["correct"] += 1
    for entry in by_mode.values():
        entry["accuracy"] = (entry["correct"] / entry["attempts"]) if entry["attempts"] else 0.0
    by_exercise: dict[str, dict] = {}
    for result, _mode, slug, _pid, _uid, at, dur in rows:
        entry = by_exercise.setdefault(
            slug,
            {
                "exercise": slug,
                "attempts": 0,
                "correct": 0,
                "accuracy": 0.0,
                "avg_response_ms": None,
                "last_practiced_at": None,
            },
        )
        entry["attempts"] += 1
        if result == "correct":
            entry["correct"] += 1
        if entry["last_practiced_at"] is None and at is not None:
            # Rows arrive in id order (oldest first); keep the newest.
            entry["last_practiced_at"] = at
        elif at is not None and at > entry["last_practiced_at"]:
            entry["last_practiced_at"] = at
    for slug, entry in by_exercise.items():
        slug_durs = [r[6] for r in rows if r[2] == slug and r[6] is not None]
        entry["avg_response_ms"] = (sum(slug_durs) / len(slug_durs)) if slug_durs else None
        entry["accuracy"] = (entry["correct"] / entry["attempts"]) if entry["attempts"] else 0.0
    return {
        "attempts": attempts,
        "correct": correct,
        "partial": partial,
        "wrong": wrong,
        "terminal": terminal,
        "accuracy": (correct / attempts) if attempts else 0.0,
        "avg_response_ms": (sum(durations) / len(durations)) if durations else None,
        "total_practice_ms": sum(durations),
        "active_days": len({r[5].date() for r in rows if r[5] is not None}),
        "by_mode": sorted(by_mode.values(), key=lambda e: e["mode"]),
        "by_exercise": sorted(by_exercise.values(), key=lambda e: e["exercise"]),
    }


def _daily_buckets(
    rows: list[tuple],
    window: Window,
    xp_rows: list[tuple] | None = None,
) -> list[dict]:
    """Per-day (or per-week for long spans) buckets over ``[start, end)``.

    ``xp_rows`` are ``(created_at, amount)`` tuples bucketed alongside.
    """
    end = window.end
    if window.start is not None:
        span_days = max(1, (end - window.start).days)
        span_start = window.start
    elif rows:
        earliest = min(r[5] for r in rows if r[5] is not None)
        span_days = max(1, (end - earliest).days + 1)
        span_start = datetime(earliest.year, earliest.month, earliest.day)
    else:
        return []
    weekly = span_days > DAILY_BUCKET_LIMIT_DAYS
    step = timedelta(days=7) if weekly else timedelta(days=1)
    buckets: list[dict] = []
    cursor = datetime(span_start.year, span_start.month, span_start.day)
    while cursor < end:
        buckets.append({"bucket_start": cursor.date().isoformat(), "attempts": 0, "correct": 0, "xp": 0})
        cursor += step
    if not buckets:
        return []
    def _index(moment: datetime) -> int | None:
        if moment < span_start or moment >= end:
            return None
        delta = moment - datetime(span_start.year, span_start.month, span_start.day)
        idx = delta.days // (7 if weekly else 1)
        return idx if 0 <= idx < len(buckets) else None
    for result, _mode, _slug, _pid, _uid, at, _dur in rows:
        if at is None:
            continue
        idx = _index(at)
        if idx is None:
            continue
        buckets[idx]["attempts"] += 1
        if result == "correct":
            buckets[idx]["correct"] += 1
    for at, amount in xp_rows or []:
        if at is None:
            continue
        idx = _index(at)
        if idx is None:
            continue
        buckets[idx]["xp"] += amount
    for bucket in buckets:
        attempts = bucket["attempts"]
        bucket["accuracy"] = (bucket["correct"] / attempts) if attempts else 0.0
    return buckets


# --- ratings / XP helpers -----------------------------------------------------


def _rating_events(db: Session, user_id: int, window: Window, exercise: str | None = None):
    q = (
        db.query(RatingEvent.exercise_slug, RatingEvent.rating_delta, RatingEvent.created_at)
        .filter(RatingEvent.user_id == user_id)
        .filter(RatingEvent.created_at < window.end)
    )
    if window.start is not None:
        q = q.filter(RatingEvent.created_at >= window.start)
    if exercise:
        q = q.filter(RatingEvent.exercise_slug == exercise)
    return q.all()


def _xp_events(db: Session, user_id: int, window: Window):
    q = (
        db.query(XpEvent.amount, XpEvent.created_at)
        .filter(XpEvent.user_id == user_id)
        .filter(XpEvent.created_at < window.end)
    )
    if window.start is not None:
        q = q.filter(XpEvent.created_at >= window.start)
    return q.all()


def _xp_summary(db: Session, user_id: int, window: Window) -> dict:
    events = _xp_events(db, user_id, window)
    state: PlayerGamificationState | None = (
        db.query(PlayerGamificationState).filter(PlayerGamificationState.user_id == user_id).first()
    )
    total = state.total_xp if state else 0
    return {
        "earned_in_period": sum(amount for amount, _at in events),
        "events_in_period": len(events),
        "total": total,
        "level": level_for_total(total),
    }


def _streak_summary(db: Session, user_id: int) -> dict:
    streak: PlayerStreak | None = (
        db.query(PlayerStreak).filter(PlayerStreak.user_id == user_id).first()
    )
    return {
        "current": streak.current_streak if streak else 0,
        "longest": streak.longest_streak if streak else 0,
    }


def _ratings_summary(
    db: Session, user_id: int, window: Window, exercise: str | None = None
) -> list[dict]:
    events = _rating_events(db, user_id, window, exercise)
    by_exercise: dict[str, dict] = {}
    for slug, delta, _at in events:
        entry = by_exercise.setdefault(slug, {"events": 0, "delta": 0.0})
        entry["events"] += 1
        entry["delta"] += delta
    q = db.query(PlayerRating).filter(PlayerRating.user_id == user_id)
    if exercise:
        q = q.filter(PlayerRating.exercise_slug == exercise)
    current = {row.exercise_slug: row for row in q.all()}
    slugs = sorted(set(by_exercise) | set(current))
    items = []
    for slug in slugs:
        row = current.get(slug)
        period = by_exercise.get(slug, {"events": 0, "delta": 0.0})
        items.append(
            {
                "exercise": slug,
                "current": row.rating if row else None,
                "provisional": bool(row.is_provisional) if row else None,
                "games": row.games_count if row else 0,
                "events_in_period": period["events"],
                "delta_in_period": round(period["delta"], 2),
            }
        )
    return items


# --- player analytics ----------------------------------------------------------


def player_overview(
    db: Session, user_id: int, window: Window, exercise: str | None = None
) -> dict:
    """Full player analytics for one window (optionally one exercise)."""
    rows = _player_attempt_rows(db, user_id, window, exercise)
    xp_events = _xp_events(db, user_id, window)
    summary = _summarize(rows)
    return {
        "period": window.period,
        "start": window.start,
        "end": window.end,
        "exercise": exercise,
        "totals": {k: v for k, v in summary.items() if k not in ("by_mode", "by_exercise")},
        "by_mode": summary["by_mode"],
        "by_exercise": summary["by_exercise"],
        "daily": _daily_buckets(rows, window, [(at, amount) for amount, at in xp_events]),
        "ratings": _ratings_summary(db, user_id, window, exercise),
        "xp": _xp_summary(db, user_id, window),
        "streak": _streak_summary(db, user_id),
    }


def player_comparison(
    db: Session, user_id: int, window: Window, exercise: str | None = None
) -> dict:
    """Current vs previous equivalent period. Bounded windows only."""
    previous = _previous_window(window)
    current_rows = _player_attempt_rows(db, user_id, window, exercise)
    previous_rows = _player_attempt_rows(db, user_id, previous, exercise)
    current = _summarize(current_rows)
    prev = _summarize(previous_rows)
    current_xp = sum(a for a, _at in _xp_events(db, user_id, window))
    prev_xp = sum(a for a, _at in _xp_events(db, user_id, previous))
    current_events = _rating_events(db, user_id, window, exercise)
    prev_events = _rating_events(db, user_id, previous, exercise)
    current_delta = round(sum(d for _s, d, _at in current_events), 2)
    prev_delta = round(sum(d for _s, d, _at in prev_events), 2)
    return {
        "period": window.period,
        "exercise": exercise,
        "current": {
            "start": window.start,
            "end": window.end,
            "attempts": current["attempts"],
            "accuracy": current["accuracy"],
            "avg_response_ms": current["avg_response_ms"],
            "active_days": current["active_days"],
            "xp_earned": current_xp,
            "rating_delta": current_delta,
        },
        "previous": {
            "start": previous.start,
            "end": previous.end,
            "attempts": prev["attempts"],
            "accuracy": prev["accuracy"],
            "avg_response_ms": prev["avg_response_ms"],
            "active_days": prev["active_days"],
            "xp_earned": prev_xp,
            "rating_delta": prev_delta,
        },
        "delta": {
            "attempts": current["attempts"] - prev["attempts"],
            "accuracy": current["accuracy"] - prev["accuracy"],
            "active_days": current["active_days"] - prev["active_days"],
            "xp_earned": current_xp - prev_xp,
            "rating_delta": round(current_delta - prev_delta, 2),
        },
    }


def player_puzzle(db: Session, user_id: int, puzzle_id: int) -> dict | None:
    """Personal stats for one puzzle. Never exposes the puzzle answer."""
    puzzle: Puzzle | None = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        return None
    rows = (
        db.query(Attempt.result, Attempt.created_at, Attempt.duration_ms)
        .filter(Attempt.user_id == user_id, Attempt.puzzle_id == puzzle_id)
        .order_by(Attempt.id)
        .all()
    )
    attempts = len(rows)
    correct = sum(1 for r, _at, _dur in rows if r == "correct")
    durations = [dur for _r, _at, dur in rows if dur is not None]
    return {
        "puzzle_id": puzzle.id,
        "exercise_slug": puzzle.exercise_slug,
        "attempts": attempts,
        "correct": correct,
        "accuracy": (correct / attempts) if attempts else 0.0,
        "avg_response_ms": (sum(durations) / len(durations)) if durations else None,
        "last_attempt_at": rows[-1][1] if rows else None,
    }


# --- observed difficulty --------------------------------------------------------


def observed_difficulty(accuracy: float, attempts: int) -> str:
    """Derived label only; never persisted on the puzzle (Phase 10 owns adaptation)."""
    if attempts < MIN_OBSERVED_ATTEMPTS:
        return "insufficient_data"
    if accuracy >= 0.7:
        return "easy"
    if accuracy >= 0.4:
        return "medium"
    return "hard"


def _puzzle_stats(rows: list[tuple]) -> dict:
    """Aggregate (result, user_id) rows for one puzzle in a window."""
    attempts = len(rows)
    correct = sum(1 for r, _u in rows if r == "correct")
    accuracy = (correct / attempts) if attempts else 0.0
    wrong_by_user: dict[int, int] = {}
    for result, user_id in rows:
        if result == "wrong":
            wrong_by_user[user_id] = wrong_by_user.get(user_id, 0) + 1
    return {
        "attempts": attempts,
        "correct": correct,
        "accuracy": accuracy,
        "failure_rate": (1.0 - accuracy) if attempts else 0.0,
        "unique_players": len({user_id for _r, user_id in rows}),
        "repeated_failures": sum(1 for count in wrong_by_user.values() if count >= 2),
        "observed_difficulty": observed_difficulty(accuracy, attempts),
    }


# --- admin analytics --------------------------------------------------------------


def _known_slugs(db: Session) -> set[str]:
    slugs = set(registry.registered_slugs())
    for (slug,) in db.query(Exercise.slug).all():
        slugs.add(slug)
    return slugs


def platform_overview(db: Session, window: Window) -> dict:
    """Aggregate platform metrics. No per-user rows leave this function."""
    rows = _platform_attempt_rows(db, window)
    summary = _summarize(rows)
    users_total = db.query(User).count()
    if window.start is not None:
        new_registrations = (
            db.query(User)
            .filter(User.created_at >= window.start, User.created_at < window.end)
            .count()
        )
    else:
        new_registrations = users_total
    rating_q = db.query(RatingEvent.rating_delta, RatingEvent.created_at).filter(
        RatingEvent.created_at < window.end
    )
    xp_q = db.query(XpEvent.amount, XpEvent.created_at).filter(XpEvent.created_at < window.end)
    if window.start is not None:
        rating_q = rating_q.filter(RatingEvent.created_at >= window.start)
        xp_q = xp_q.filter(XpEvent.created_at >= window.start)
    rating_rows = rating_q.all()
    xp_rows = xp_q.all()
    exercise_usage = []
    for entry in summary["by_exercise"]:
        slug = entry["exercise"]
        players = len({r[4] for r in rows if r[2] == slug})
        exercise_usage.append({**entry, "unique_players": players})
    comparison = None
    if window.start is not None and window.days:
        previous = _previous_window(window)
        prev_rows = _platform_attempt_rows(db, previous)
        prev = _summarize(prev_rows)
        prev_xp = db.query(XpEvent.amount).filter(
            XpEvent.created_at >= previous.start, XpEvent.created_at < previous.end
        ).all()
        comparison = {
            "attempts": summary["attempts"] - prev["attempts"],
            "accuracy": summary["accuracy"] - prev["accuracy"],
            "active_users": len({r[4] for r in rows}) - len({r[4] for r in prev_rows}),
            "xp_earned": sum(a for a, _at in xp_rows) - sum(a for (a,) in prev_xp),
        }
    return {
        "period": window.period,
        "start": window.start,
        "end": window.end,
        "users_total": users_total,
        "new_registrations": new_registrations,
        "active_users": len({r[4] for r in rows}),
        "totals": {k: v for k, v in summary.items() if k not in ("by_mode", "by_exercise")},
        "by_mode": summary["by_mode"],
        "exercise_usage": sorted(exercise_usage, key=lambda e: e["exercise"]),
        "daily": _daily_buckets(rows, window, [(at, amount) for amount, at in xp_rows]),
        "ratings": {
            "events_in_period": len(rating_rows),
            "delta_sum_in_period": round(sum(d for d, _at in rating_rows), 2),
            "current_rows": db.query(PlayerRating).count(),
        },
        "xp": {
            "earned_in_period": sum(a for a, _at in xp_rows),
            "events_in_period": len(xp_rows),
        },
        "comparison": comparison,
    }


def exercise_overview(db: Session, window: Window) -> list[dict]:
    """One aggregate row per known exercise (compact; no daily buckets)."""
    rows = _platform_attempt_rows(db, window)
    catalog = {row.slug: row for row in db.query(Exercise).all()}
    rating_rows = (
        db.query(RatingEvent.exercise_slug, RatingEvent.rating_delta)
        .filter(RatingEvent.created_at < window.end)
    )
    if window.start is not None:
        rating_rows = rating_rows.filter(RatingEvent.created_at >= window.start)
    rating_by_exercise: dict[str, dict] = {}
    for slug, delta in rating_rows.all():
        entry = rating_by_exercise.setdefault(slug, {"events": 0, "delta": 0.0})
        entry["events"] += 1
        entry["delta"] += delta
    current_ratings = db.query(PlayerRating.exercise_slug, PlayerRating.rating).all()
    current_by_exercise: dict[str, list[float]] = {}
    for slug, rating in current_ratings:
        current_by_exercise.setdefault(slug, []).append(rating)
    items = []
    for slug in sorted(_known_slugs(db)):
        scoped = [r for r in rows if r[2] == slug]
        stats = _summarize(scoped)
        exercise = catalog.get(slug)
        puzzles_total = (
            db.query(Puzzle).filter(Puzzle.exercise_slug == slug).count()
        )
        puzzles_published = (
            db.query(Puzzle)
            .filter(
                Puzzle.exercise_slug == slug,
                Puzzle.is_published == True,  # noqa: E712
                Puzzle.is_archived == False,  # noqa: E712
            )
            .count()
        )
        rating_period = rating_by_exercise.get(slug, {"events": 0, "delta": 0.0})
        current = current_by_exercise.get(slug, [])
        items.append(
            {
                "exercise": slug,
                "is_active": bool(exercise.is_active) if exercise is not None else None,
                "attempts": stats["attempts"],
                "unique_players": len({r[4] for r in scoped}),
                "correct": stats["correct"],
                "partial": stats["partial"],
                "wrong": stats["wrong"],
                "accuracy": stats["accuracy"],
                "avg_response_ms": stats["avg_response_ms"],
                "active_days": stats["active_days"],
                "puzzles_total": puzzles_total,
                "puzzles_published": puzzles_published,
                "rating_events_in_period": rating_period["events"],
                "rating_delta_sum_in_period": round(rating_period["delta"], 2),
                "current_ratings": len(current),
                "current_rating_avg": (sum(current) / len(current)) if current else None,
            }
        )
    return items


def exercise_detail(db: Session, slug: str, window: Window) -> dict | None:
    """One exercise with daily usage trend and rating progression."""
    if slug not in _known_slugs(db):
        return None
    rows = [r for r in _platform_attempt_rows(db, window) if r[2] == slug]
    stats = _summarize(rows)
    rating_events = (
        db.query(RatingEvent.rating_delta, RatingEvent.created_at)
        .filter(RatingEvent.exercise_slug == slug, RatingEvent.created_at < window.end)
    )
    xp_for_scope = None  # XP is not scoped per exercise (events link attempts, not exercises).
    if window.start is not None:
        rating_events = rating_events.filter(RatingEvent.created_at >= window.start)
    deltas = [d for d, _at in rating_events.all()]
    current = [r for (r,) in db.query(PlayerRating.rating).filter(PlayerRating.exercise_slug == slug).all()]
    _ = xp_for_scope
    puzzles_total = db.query(Puzzle).filter(Puzzle.exercise_slug == slug).count()
    puzzles_published = (
        db.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == slug,
            Puzzle.is_published == True,  # noqa: E712
            Puzzle.is_archived == False,  # noqa: E712
        )
        .count()
    )
    catalog_row = db.get(Exercise, slug)
    supply_rows = (
        db.query(Puzzle.status, func.count(Puzzle.id))
        .filter(Puzzle.exercise_slug == slug)
        .group_by(Puzzle.status)
        .all()
    )
    difficulty_rows = (
        db.query(Puzzle.difficulty, func.count(Puzzle.id))
        .filter(Puzzle.exercise_slug == slug)
        .group_by(Puzzle.difficulty)
        .all()
    )
    mistake_query = (
        db.query(Evidence.mistake_core, func.count(Evidence.id))
        .filter(Evidence.exercise_slug == slug, Evidence.observed_at < window.end)
    )
    if window.start is not None:
        mistake_query = mistake_query.filter(Evidence.observed_at >= window.start)
    mistake_rows = (
        mistake_query.group_by(Evidence.mistake_core)
        .order_by(func.count(Evidence.id).desc())
        .limit(10)
        .all()
    )
    recommendation_query = (
        db.query(AdaptiveRecommendation.status, func.count(AdaptiveRecommendation.id))
        .filter(
            AdaptiveRecommendation.exercise_slug == slug,
            AdaptiveRecommendation.created_at < window.end,
        )
    )
    if window.start is not None:
        recommendation_query = recommendation_query.filter(
            AdaptiveRecommendation.created_at >= window.start
        )
    recommendation_rows = recommendation_query.group_by(AdaptiveRecommendation.status).all()
    return {
        "exercise": slug,
        "is_active": bool(catalog_row.is_active) if catalog_row is not None else None,
        "period": window.period,
        "start": window.start,
        "end": window.end,
        "puzzles_total": puzzles_total,
        "puzzles_published": puzzles_published,
        "supply_by_status": [
            {"status": status, "count": int(count)} for status, count in supply_rows
        ],
        "difficulty_distribution": [
            {"difficulty": difficulty, "count": int(count)}
            for difficulty, count in difficulty_rows
        ],
        "mistake_distribution": [
            {"mistake": mistake or "none", "count": int(count)}
            for mistake, count in mistake_rows
        ],
        "recommendation_outcomes": [
            {"status": status, "count": int(count)}
            for status, count in recommendation_rows
        ],
        "attempts": stats["attempts"],
        "unique_players": len({r[4] for r in rows}),
        "correct": stats["correct"],
        "partial": stats["partial"],
        "wrong": stats["wrong"],
        "terminal": stats["terminal"],
        "accuracy": stats["accuracy"],
        "avg_response_ms": stats["avg_response_ms"],
        "total_practice_ms": stats["total_practice_ms"],
        "active_days": stats["active_days"],
        "by_mode": stats["by_mode"],
        "daily": _daily_buckets(rows, window),
        "rating_events_in_period": len(deltas),
        "rating_delta_sum_in_period": round(sum(deltas), 2),
        "current_ratings": len(current),
        "current_rating_avg": (sum(current) / len(current)) if current else None,
    }


def puzzle_list(
    db: Session,
    window: Window,
    exercise: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[dict]:
    """Paginated per-puzzle aggregates. Never includes answer data."""
    query = db.query(Puzzle)
    if exercise:
        query = query.filter(Puzzle.exercise_slug == exercise)
    puzzles = query.order_by(Puzzle.id).offset((page - 1) * page_size).limit(page_size).all()
    if not puzzles:
        return []
    ids = [p.id for p in puzzles]
    attempt_q = (
        db.query(Attempt.puzzle_id, Attempt.result, Attempt.user_id, Attempt.duration_ms)
        .filter(Attempt.puzzle_id.in_(ids), Attempt.user_id.is_not(None))
        .filter(Attempt.created_at < window.end)
    )
    if window.start is not None:
        attempt_q = attempt_q.filter(Attempt.created_at >= window.start)
    if exercise:
        attempt_q = attempt_q.filter(Attempt.exercise_slug == exercise)
    by_puzzle: dict[int, list[tuple]] = {pid: [] for pid in ids}
    durations: dict[int, list[int]] = {pid: [] for pid in ids}
    for puzzle_id, result, user_id, duration_ms in attempt_q.all():
        by_puzzle[puzzle_id].append((result, user_id))
        if duration_ms is not None:
            durations[puzzle_id].append(duration_ms)
    items = []
    for puzzle in puzzles:
        stats = _puzzle_stats(by_puzzle[puzzle.id])
        durs = durations[puzzle.id]
        items.append(
            {
                "puzzle_id": puzzle.id,
                "exercise_slug": puzzle.exercise_slug,
                "status": puzzle.status or "draft",
                "difficulty": puzzle.difficulty,
                "initial_rating": puzzle.initial_rating,
                **stats,
                "avg_response_ms": (sum(durs) / len(durs)) if durs else None,
            }
        )
    return items


def puzzle_detail(db: Session, puzzle_id: int, window: Window) -> dict | None:
    """One puzzle with daily trend. Never includes answer data."""
    puzzle: Puzzle | None = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        return None
    attempt_q = (
        db.query(
            Attempt.result,
            Attempt.mode,
            Attempt.exercise_slug,
            Attempt.puzzle_id,
            Attempt.user_id,
            Attempt.created_at,
            Attempt.duration_ms,
        )
        .filter(Attempt.puzzle_id == puzzle_id, Attempt.user_id.is_not(None))
        .filter(Attempt.created_at < window.end)
    )
    if window.start is not None:
        attempt_q = attempt_q.filter(Attempt.created_at >= window.start)
    rows = attempt_q.order_by(Attempt.id).all()
    summary = _summarize(rows)
    stats = _puzzle_stats([(r[0], r[4]) for r in rows])
    return {
        "puzzle_id": puzzle.id,
        "exercise_slug": puzzle.exercise_slug,
        "status": puzzle.status or "draft",
        "difficulty": puzzle.difficulty,
        "initial_rating": puzzle.initial_rating,
        "period": window.period,
        "start": window.start,
        "end": window.end,
        **stats,
        "avg_response_ms": summary["avg_response_ms"],
        "by_mode": summary["by_mode"],
        "daily": _daily_buckets(rows, window),
    }
