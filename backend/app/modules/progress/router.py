"""Attempt routes: thin handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.progress import schemas, service

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=schemas.AttemptOut)
def create_attempt(
    body: schemas.AttemptIn,
    db: Session = Depends(get_db),
    # Guest/anonymous practice is disabled: only authenticated accounts
    # hold ATTEMPTS_SUBMIT, so guests get 401 here and never reach the
    # service (no attempt, no evidence). Historical guest rows are kept.
    user=Depends(require_capability(Capability.ATTEMPTS_SUBMIT)),
):
    try:
        attempt, feedback_key, detail = service.submit_attempt(
            db,
            user_id=user.id,
            puzzle_id=body.puzzle_id,
            answer=body.answer,
            mode=body.mode,
            client_result=body.client_result,
            hints_used=body.hints_used,
            started_at=body.started_at,
        )
    except ValueError as exc:
        if str(exc) == "auth_required":
            raise HTTPException(status_code=401, detail="auth_required")
        if str(exc) == "attempt_owner_conflict":
            raise HTTPException(status_code=400, detail="attempt_owner_conflict")
        if str(exc) == "exercise_not_available":
            raise HTTPException(status_code=404, detail="exercise_not_available")
        raise HTTPException(status_code=404, detail="puzzle_not_available")
    out = schemas.AttemptOut.model_validate(attempt)
    out.feedback_key = feedback_key
    out.detail = detail
    return out
