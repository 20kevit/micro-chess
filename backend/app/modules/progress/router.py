"""Attempt routes: thin handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.progress import schemas, service
from app.modules.rule_engine.base import AttemptMode

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=schemas.AttemptOut)
def create_attempt(
    body: schemas.AttemptIn,
    db: Session = Depends(get_db),
    user=Depends(require_capability(Capability.ATTEMPTS_SUBMIT, allow_anonymous=True)),
):
    if body.mode == AttemptMode.RATED and user is None:
        raise HTTPException(status_code=401, detail="auth_required_for_rated")
    try:
        attempt, feedback_key, detail = service.submit_attempt(
            db,
            user_id=user.id if user else None,
            puzzle_id=body.puzzle_id,
            answer=body.answer,
            mode=body.mode,
            client_result=body.client_result,
            hints_used=body.hints_used,
            started_at=body.started_at,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="puzzle_not_available")
    out = schemas.AttemptOut.model_validate(attempt)
    out.feedback_key = feedback_key
    out.detail = detail
    return out
