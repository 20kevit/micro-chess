"""Attempt routes: thin handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional, get_db
from app.modules.progress import schemas, service
from app.modules.rule_engine.base import AttemptMode

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=schemas.AttemptOut)
def create_attempt(body: schemas.AttemptIn, db: Session = Depends(get_db), user=Depends(get_current_user_optional)):
    if body.mode == AttemptMode.RATED and user is None:
        raise HTTPException(status_code=401, detail="auth_required_for_rated")
    try:
        attempt, feedback_key = service.submit_attempt(
            db,
            user_id=user.id if user else None,
            puzzle_id=body.puzzle_id,
            answer=body.answer,
            mode=body.mode,
            client_result=body.client_result,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="puzzle_not_available")
    out = schemas.AttemptOut.model_validate(attempt)
    out.feedback_key = feedback_key
    return out
