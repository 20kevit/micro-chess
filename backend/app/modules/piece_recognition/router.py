"""Piece Recognition routes: practice next-puzzle + speed sessions.

Thin wiring only; generation/clock/scoring live in generator/sessions and
the shared progress service. The authoritative answer is never exposed:
``next`` endpoints return ``PuzzleOut`` (no ``answer_json``).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional, get_db
from app.modules.piece_recognition import schemas, sessions
from app.modules.piece_recognition.sessions import (
    PuzzleAlreadyAnsweredError,
    PuzzleNotInSessionError,
    SessionExpiredError,
    SessionNotFoundError,
)
from app.modules.progress.schemas import AttemptOut
from app.modules.puzzles.schemas import PuzzleOut

router = APIRouter(prefix="/piece-recognition", tags=["piece-recognition"])


def _to_out(session: sessions.PieceSpeedSession) -> schemas.SessionOut:
    data = sessions.summary(session)
    return schemas.SessionOut(**data)


def _to_summary(session: sessions.PieceSpeedSession) -> schemas.SessionSummary:
    return schemas.SessionSummary(**sessions.summary(session))


@router.post("/next", response_model=PuzzleOut)
def next_practice_puzzle(db: Session = Depends(get_db)):
    """Issue one fresh random puzzle for untimed Practice Mode."""
    return sessions.issue_practice_puzzle(db)


@router.post("/sessions", response_model=schemas.SessionOut)
def start_speed_session(
    body: schemas.SessionStartIn | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    session = sessions.start_session(
        db,
        user_id=user.id if user else None,
        duration_s=body.duration_s if body else None,
    )
    return _to_out(session)


@router.get("/sessions/{session_id}", response_model=schemas.SessionSummary)
def get_speed_session(session_id: str, db: Session = Depends(get_db)):
    try:
        return _to_summary(sessions.get_session(db, session_id))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")


@router.post("/sessions/{session_id}/next", response_model=PuzzleOut)
def next_speed_puzzle(session_id: str, db: Session = Depends(get_db)):
    try:
        return sessions.issue_puzzle(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="session_expired")


@router.post("/sessions/{session_id}/submit", response_model=schemas.SessionSubmitOut)
def submit_speed_answer(
    session_id: str,
    body: schemas.SessionSubmitIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    try:
        attempt, feedback_key, detail, session = sessions.submit(
            db,
            session_id,
            user_id=user.id if user else None,
            puzzle_id=body.puzzle_id,
            answer=body.answer,
            hints_used=body.hints_used,
            started_at=body.started_at,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="session_expired")
    except PuzzleNotInSessionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PuzzleAlreadyAnsweredError:
        raise HTTPException(status_code=409, detail="puzzle_already_answered")
    out = AttemptOut.model_validate(attempt)
    out.feedback_key = feedback_key
    out.detail = detail
    return schemas.SessionSubmitOut(
        attempt=out,
        feedback_key=feedback_key,
        detail=detail,
        session=_to_summary(session),
    )


@router.post("/sessions/{session_id}/finish", response_model=schemas.SessionSummary)
def finish_speed_session(session_id: str, db: Session = Depends(get_db)):
    try:
        return _to_summary(sessions.finish(db, session_id))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
