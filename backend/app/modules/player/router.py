"""Player platform routes: thin handlers delegating to the player service.

Every endpoint is scoped to the authenticated account (``/me/*``): the
identity comes from the server-validated session, never from a
client-supplied user id. Missing-or-foreign resources uniformly return
404 so one player cannot probe another player's data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.modules.analytics import schemas as analytics_schemas
from app.modules.analytics import service as analytics_service
from app.modules.gamification_engine import service as gamification_service
from app.modules.player import schemas, service
from app.modules.rating_engine import service as ratings_service
from app.modules.rule_engine.base import AttemptMode
from app.modules.users.models import User

router = APIRouter(prefix="/me", tags=["player"])


def _conflict(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in ("identity_exists", "identity_taken"):
        return HTTPException(status_code=409, detail=code)
    if code == "unknown_provider":
        return HTTPException(status_code=422, detail=code)
    return HTTPException(status_code=422, detail=code)


# --- profile ---------------------------------------------------------------


@router.get("/profile", response_model=schemas.ProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.get_or_create_profile(db, user)


@router.patch("/profile", response_model=schemas.ProfileOut)
def patch_profile(
    body: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.update_profile(
            db,
            user,
            display_name=body.display_name,
            bio=body.bio,
            avatar_reference=body.avatar_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- external chess identities ----------------------------------------------


@router.get("/chess-identities", response_model=list[schemas.IdentityOut])
def list_identities(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return [schemas.identity_to_out(row) for row in service.list_identities(db, user)]


@router.post("/chess-identities", response_model=schemas.IdentityOut, status_code=201)
def add_identity(
    body: schemas.IdentityIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        identity = service.add_identity(
            db,
            user,
            provider=body.provider,
            username=body.username,
            rating=body.rating,
            rating_type=body.rating_type,
        )
    except ValueError as exc:
        raise _conflict(exc)
    return schemas.identity_to_out(identity)


@router.patch("/chess-identities/{identity_id}", response_model=schemas.IdentityOut)
def patch_identity(
    identity_id: int,
    body: schemas.IdentityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    provided = body.provided()
    try:
        identity = service.update_identity(
            db,
            user,
            identity_id,
            username=body.username,
            username_set="username" in provided,
            rating=body.rating,
            rating_set="rating" in provided,
            rating_type=body.rating_type,
            rating_type_set="rating_type" in provided,
        )
    except ValueError as exc:
        raise _conflict(exc)
    if identity is None:
        raise HTTPException(status_code=404, detail="identity_not_found")
    return schemas.identity_to_out(identity)


@router.delete("/chess-identities/{identity_id}", status_code=204)
def delete_identity(
    identity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    if not service.delete_identity(db, user, identity_id):
        raise HTTPException(status_code=404, detail="identity_not_found")
    return None


# --- training history --------------------------------------------------------


@router.get("/training/attempts", response_model=list[schemas.HistoryAttemptOut])
def list_history(
    exercise: str | None = None,
    mode: AttemptMode | None = None,
    correct: bool | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_attempts(
        db, user, exercise=exercise, mode=mode, correct=correct, page=page, page_size=page_size
    )


@router.get("/training/attempts/{attempt_id}", response_model=schemas.HistoryAttemptOut)
def get_history_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    attempt = service.get_attempt(db, user, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt_not_found")
    return attempt


# --- progress -----------------------------------------------------------------


@router.get("/progress", response_model=schemas.ProgressOut)
def get_progress(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.progress_summary(db, user)


@router.get("/progress/{exercise_slug}", response_model=schemas.ExerciseProgressOut)
def get_exercise_progress(
    exercise_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    progress = service.exercise_progress(db, user, exercise_slug)
    if progress is None:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    return progress


# --- ratings ------------------------------------------------------------------------


@router.get("/ratings", response_model=schemas.RatingsOut)
def list_ratings(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    rows = ratings_service.list_ratings(db, user.id)
    return schemas.RatingsOut(items=[schemas.rating_to_out(row) for row in rows])


@router.get("/ratings/{exercise_slug}", response_model=schemas.RatingOut)
def get_rating(
    exercise_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    if not service.is_known_exercise(db, exercise_slug):
        raise HTTPException(status_code=404, detail="exercise_not_found")
    row = ratings_service.get_rating(db, user.id, exercise_slug)
    if row is None:
        raise HTTPException(status_code=404, detail="rating_not_found")
    return schemas.rating_to_out(row)


@router.get("/ratings/{exercise_slug}/history", response_model=schemas.RatingHistoryOut)
def get_rating_history(
    exercise_slug: str,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    if not service.is_known_exercise(db, exercise_slug):
        raise HTTPException(status_code=404, detail="exercise_not_found")
    rows = ratings_service.list_history(
        db, user.id, exercise_slug, page=page, page_size=page_size
    )
    return schemas.RatingHistoryOut(items=[schemas.rating_event_to_out(row) for row in rows])


# --- gamification ---------------------------------------------------------------------


@router.get("/gamification", response_model=schemas.GamificationSummaryOut)
def get_gamification(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    state = gamification_service.get_state(db, user.id)
    total = state.total_xp if state else 0
    level = state.level if state else 1
    in_level, for_next = gamification_service.xp_progress_in_level(total)
    streak = gamification_service.get_streak(db, user.id)
    unlocks = gamification_service.list_unlocks(db, user.id)
    return schemas.GamificationSummaryOut(
        xp=schemas.GamificationXpOut(
            total=total, level=level, xp_in_level=in_level, xp_for_next=for_next
        ),
        streak=schemas.GamificationStreakOut(
            current=streak.current_streak if streak else 0,
            longest=streak.longest_streak if streak else 0,
        ),
        achievements_unlocked=len(unlocks),
        total_achievements=len(gamification_service.ACHIEVEMENTS),
    )


@router.get("/gamification/xp", response_model=schemas.XpHistoryOut)
def get_xp_history(
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    rows = gamification_service.list_xp_history(db, user.id, page=page, page_size=page_size)
    return schemas.XpHistoryOut(items=[schemas.xp_event_to_out(row) for row in rows])


@router.get("/achievements", response_model=schemas.AchievementsOut)
def list_achievements(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    unlocked = {row.achievement_code: row for row in gamification_service.list_unlocks(db, user.id)}
    return schemas.AchievementsOut(
        items=[
            schemas.AchievementOut(
                code=definition.code,
                unlocked=definition.code in unlocked,
                unlocked_at=unlocked[definition.code].unlocked_at
                if definition.code in unlocked
                else None,
            )
            for definition in gamification_service.ACHIEVEMENTS
        ]
    )


# --- analytics (Phase 8, read-only derived metrics) -----------------------------


def _analytics_window(period: str, date_from: str | None, date_to: str | None):
    try:
        return analytics_service.resolve_window(period, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/analytics", response_model=analytics_schemas.PlayerAnalyticsOut)
def get_analytics(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    exercise: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    window = _analytics_window(period, date_from, date_to)
    if exercise is not None and not service.is_known_exercise(db, exercise):
        raise HTTPException(status_code=404, detail="exercise_not_found")
    return analytics_service.player_overview(db, user.id, window, exercise)


@router.get("/analytics/comparison", response_model=analytics_schemas.PlayerComparisonOut)
def get_analytics_comparison(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    exercise: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    window = _analytics_window(period, date_from, date_to)
    if exercise is not None and not service.is_known_exercise(db, exercise):
        raise HTTPException(status_code=404, detail="exercise_not_found")
    try:
        return analytics_service.player_comparison(db, user.id, window, exercise)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/analytics/exercises/{exercise_slug}",
    response_model=analytics_schemas.PlayerAnalyticsOut,
)
def get_analytics_exercise(
    exercise_slug: str,
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    if not service.is_known_exercise(db, exercise_slug):
        raise HTTPException(status_code=404, detail="exercise_not_found")
    window = _analytics_window(period, date_from, date_to)
    return analytics_service.player_overview(db, user.id, window, exercise_slug)


@router.get(
    "/analytics/puzzles/{puzzle_id}",
    response_model=analytics_schemas.PlayerPuzzleAnalyticsOut,
)
def get_analytics_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    stats = analytics_service.player_puzzle(db, user.id, puzzle_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="puzzle_not_found")
    return stats


# --- dashboard ------------------------------------------------------------------


@router.get("/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    data = service.dashboard(db, user)
    return schemas.DashboardOut(
        profile=data["profile"],
        progress=data["progress"],
        recent_attempts=data["recent_attempts"],
    )
