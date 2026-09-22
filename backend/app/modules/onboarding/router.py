"""Onboarding routes: thin wiring over the service."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.onboarding import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["onboarding"])


@router.get("/me/onboarding", response_model=schemas.OnboardingOut)
def get_onboarding(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.view_of(service.get_or_create(db, user.id))


@router.put("/me/onboarding", response_model=schemas.OnboardingOut)
def put_onboarding(
    body: schemas.OnboardingIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        row = service.save_onboarding(
            db, user,
            experience=body.experience, play_frequency=body.play_frequency,
            fide_rating=body.fide_rating, lichess_username=body.lichess_username,
            chesscom_username=body.chesscom_username, goal=body.goal,
            intensity=body.intensity, timezone_name=body.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return service.view_of(row)


@router.get("/me/placement", response_model=list[schemas.PlacementItemOut])
def get_placement(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.placement_items(db, user.id)


@router.post("/me/placement/complete", response_model=schemas.OnboardingOut)
def complete_placement(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.view_of(service.complete_placement(db, user.id))


@router.get("/me/plan", response_model=schemas.PlanOut)
def get_plan(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.plan_view(db, user)
