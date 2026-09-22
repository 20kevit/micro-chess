"""Onboarding + placement service (P11).

Reuses existing infrastructure: player external identities (placement
signal), recommendation engine (candidate selection), rating engine
(authoritative correction). No new rating system, no random unvalidated
puzzle generation, no user-facing numeric rating.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.onboarding.models import (
    EXPERIENCES,
    GOALS,
    INTENSITIES,
    PLAY_FREQUENCIES,
    OnboardingProfile,
)
from app.modules.player import service as player_service
from app.modules.recommendations import service as rec_service
from app.modules.users.models import User

PLACEMENT_COUNT = 3


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean(value: object, limit: int = 100) -> str:
    return (value or "").strip()[:limit] if isinstance(value, str) else ""


def get_or_create(db: Session, user_id: int) -> OnboardingProfile:
    row = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user_id).first()
    if row is None:
        row = OnboardingProfile(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _validate_enum(value: str, allowed: tuple[str, ...], field: str) -> str:
    v = (value or "").strip().lower()
    if v and v not in allowed:
        raise ValueError(f"{field}_invalid")
    return v


def save_onboarding(
    db: Session,
    user: User,
    *,
    experience: str = "",
    play_frequency: str = "",
    fide_rating: int | None = None,
    lichess_username: str = "",
    chesscom_username: str = "",
    goal: str = "",
    intensity: str = "standard",
    timezone_name: str = "Asia/Tehran",
) -> OnboardingProfile:
    exp = _validate_enum(experience, EXPERIENCES, "experience")
    freq = _validate_enum(play_frequency, PLAY_FREQUENCIES, "play_frequency")
    goal_v = _validate_enum(goal, GOALS, "goal")
    inten = (intensity or "standard").strip().lower() or "standard"
    if inten not in INTENSITIES:
        raise ValueError("intensity_invalid")
    tz = _clean(timezone_name, 60) or "Asia/Tehran"
    fide = None
    if fide_rating is not None:
        try:
            fide = int(fide_rating)
        except (TypeError, ValueError):
            raise ValueError("fide_rating_invalid")
        if not 300 <= fide <= 3000:
            raise ValueError("fide_rating_invalid")
    lichess = _clean(lichess_username).lower()
    chesscom = _clean(chesscom_username).lower()
    row = get_or_create(db, user.id)
    row.experience = exp
    row.play_frequency = freq
    row.fide_rating = fide
    row.lichess_username = lichess
    row.chesscom_username = chesscom
    row.goal = goal_v
    row.intensity = inten
    row.timezone = tz
    row.onboarding_completed = True
    row.completed_at = _utcnow()
    # Mirror external signals into the canonical player identities table
    # (best-effort, reuse existing system; self-report only, unverified).
    try:
        if fide is not None:
            _upsert_identity(db, user, "fide", str(fide), fide)
        if lichess:
            _upsert_identity(db, user, "lichess", lichess, None)
        if chesscom:
            _upsert_identity(db, user, "chess_com", chesscom, None)
    except ValueError:
        pass  # identity collisions never block onboarding
    # Persist user timezone for local-day quest boundaries.
    try:
        user.timezone = tz
        db.flush()
    except Exception:
        pass
    db.commit()
    db.refresh(row)
    return row


def _upsert_identity(db: Session, user: User, provider: str, username: str, rating: int | None) -> None:
    existing = player_service.list_identities(db, user)
    for row in existing:
        if row.provider == provider:
            player_service.update_identity(
                db, user, row.id, username=username, username_set=True,
                rating=rating, rating_set=rating is not None,
                rating_type=None, rating_type_set=False,
            )
            return
    player_service.add_identity(db, user, provider=provider, username=username, rating=rating, rating_type=None)


def initial_ability_hint(db: Session, user: User) -> dict:
    """Initial ability estimate from available signals (not absolute truth).

    Priority: strongest external rating (player identities incl. FIDE
    from onboarding) else experience self-report mapping. Never exposed
    numerically to the client; callers use it only to seed selection.
    """
    placement = rec_service._placement_rating(db, user.id)  # reuse canonical signal
    if placement is not None:
        return {"source": "external", "ability": float(placement)}
    row = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user.id).first()
    exp = row.experience if row else ""
    mapping = {"new": 800.0, "beginner": 1000.0, "club": 1300.0, "advanced": 1500.0}
    return {"source": "self_report" if exp else "default", "ability": mapping.get(exp, 1200.0)}


def placement_items(db: Session, user_id: int) -> list[dict]:
    """Short placement sequence: 3 deterministic recommendations.

    Uses the existing recommendation engine repeatedly while avoiding
    duplicate exercises, so placement content is always real published
    puzzles and selection logic is never duplicated.
    """
    seen: set[str] = set()
    items: list[dict] = []
    for _ in range(PLACEMENT_COUNT):
        rec = rec_service.recommend_for_user(db, user_id)
        if rec is None or rec.puzzle_id is None:
            break
        if rec.exercise_slug in seen:
            # Nudge: pick next-best by temporarily hiding seen exercises
            # is out of scope; stop rather than duplicate.
            break
        seen.add(rec.exercise_slug)
        items.append(
            {"exercise_slug": rec.exercise_slug, "puzzle_id": rec.puzzle_id, "reason": rec.reason}
        )
        if len(items) >= PLACEMENT_COUNT:
            break
    return items


def complete_placement(db: Session, user_id: int) -> OnboardingProfile:
    row = get_or_create(db, user_id)
    row.placement_completed = True
    db.commit()
    db.refresh(row)
    return row


def plan_view(db: Session, user: User) -> dict:
    """Simple user-facing training plan (no internal scores/terminology)."""
    row = get_or_create(db, user.id)
    rec = rec_service.recommend_for_user(db, user.id)
    focus_exercise = rec.exercise_slug if rec else None
    goal_text = {
        "fun": "بازی‌های کوتاه و سرگرم‌کننده",
        "improve": "تقویت قدم‌به‌قدم مهارت‌ها",
        "compete": "آمادگی برای بازی جدی‌تر",
        "coach": "تمرین منظم برای کلاس",
    }.get(row.goal, "تقویت قدم‌به‌قدم مهارت‌ها")
    return {
        "onboarding_completed": bool(row.onboarding_completed),
        "placement_completed": bool(row.placement_completed),
        "intensity": row.intensity or "standard",
        "goal_text": goal_text,
        "focus_exercise": focus_exercise,
        "headline": "مسیر پیشنهادی تو",
        "summary": (
            "از تمرین‌های کوتاه شروع می‌کنیم؛ اول روی نقطه‌ای کار می‌کنیم که "
            "الان بیشتر به کارت می‌آید، بعد با مرور و چالش کوچک جلو می‌رویم."
        ),
    }


def view_of(row: OnboardingProfile) -> dict:
    return {
        "experience": row.experience,
        "play_frequency": row.play_frequency,
        "fide_rating": row.fide_rating,
        "lichess_username": row.lichess_username,
        "chesscom_username": row.chesscom_username,
        "goal": row.goal,
        "intensity": row.intensity,
        "timezone": row.timezone,
        "onboarding_completed": bool(row.onboarding_completed),
        "placement_completed": bool(row.placement_completed),
    }
