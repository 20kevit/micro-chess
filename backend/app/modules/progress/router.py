"""Attempt routes: thin handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db, get_guest_session_optional
from app.modules.auth.models import GuestSession
from app.modules.progress import schemas, service
from app.modules.rule_engine.base import AttemptMode

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=schemas.AttemptOut)
def create_attempt(
    body: schemas.AttemptIn,
    db: Session = Depends(get_db),
    user=Depends(require_capability(Capability.ATTEMPTS_SUBMIT, allow_anonymous=True)),
    guest: GuestSession | None = Depends(get_guest_session_optional),
):
    if body.mode == AttemptMode.RATED and user is None:
        raise HTTPException(status_code=401, detail="auth_required_for_rated")
    try:
        attempt, feedback_key, detail = service.submit_attempt(
            db,
            user_id=user.id if user else None,
            guest_session_id=guest.id if (user is None and guest is not None) else None,
            puzzle_id=body.puzzle_id,
            answer=body.answer,
            mode=body.mode,
            client_result=body.client_result,
            hints_used=body.hints_used,
            started_at=body.started_at,
        )
    except ValueError as exc:
        if str(exc) == "attempt_owner_conflict":
            raise HTTPException(status_code=400, detail="attempt_owner_conflict")
        if str(exc) == "exercise_not_available":
            raise HTTPException(status_code=404, detail="exercise_not_available")
        raise HTTPException(status_code=404, detail="puzzle_not_available")
    out = schemas.AttemptOut.model_validate(attempt)
    out.feedback_key = feedback_key
    out.detail = detail
    return out
