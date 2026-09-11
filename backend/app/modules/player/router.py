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
from app.modules.player import schemas, service
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
