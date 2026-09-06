"""Giving Check routes: practice next-puzzle + speed sessions.

Thin wiring only; generation/clock/scoring live in generator/sessions and
the shared progress service. The authoritative answer is never exposed:
``next`` endpoints return ``PuzzleOut`` (no ``answer_json``).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional, get_db
from app.modules.progress.schemas import AttemptOut
from app.modules.puzzles.schemas import PuzzleOut
from app.modules.give_check import schemas, sessions
from app.modules.give_check.sessions import (
    BufferNotReadyError,
    PuzzleAlreadyAnsweredError,
    PuzzleNotInSessionError,
    SessionExpiredError,
    SessionNotActiveError,
    SessionNotFoundError,
)

router = APIRouter(prefix="/giving-check", tags=["giving-check"])


def _to_out(session: sessions.GivingCheckSpeedSession) -> schemas.SessionOut:
    data = sessions.summary(session)
    return schemas.SessionOut(**data)


def _to_summary(session: sessions.GivingCheckSpeedSession) -> schemas.SessionSummary:
    return schemas.SessionSummary(**sessions.summary(session))


@router.post("/next", response_model=PuzzleOut)
def next_practice_puzzle(
    body: schemas.NextPracticeIn | None = None, db: Session = Depends(get_db)
):
    """Issue one fresh random puzzle for untimed Practice Mode."""
    from app.modules.give_check import generator

    exclude = set(body.exclude_ids) if body else set()
    return generator.create_puzzle(db, exclude_ids=exclude)


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
    except (SessionExpiredError, SessionNotActiveError) as exc:
        raise HTTPException(
            status_code=410 if isinstance(exc, SessionExpiredError) else 409,
            detail=str(exc),
        )


@router.post("/sessions/{session_id}/puzzles", response_model=list[PuzzleOut])
def prepare_speed_puzzles(
    session_id: str, body: schemas.PrepareIn | None = None, db: Session = Depends(get_db)
):
    """Prepare ``count`` puzzles into the session buffer (initial >=20
    before start, background refill while active). Never leaks answers."""
    try:
        return sessions.prepare_puzzles(
            db, session_id, count=body.count if body else sessions.MIN_START_BUFFER
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="session_expired")


@router.post("/sessions/{session_id}/start", response_model=schemas.SessionOut)
def start_speed_session_clock(session_id: str, db: Session = Depends(get_db)):
    """Start the authoritative clock. Requires the minimum buffer, so
    preparation time is never billed to the 60 seconds."""
    try:
        return _to_out(sessions.begin_session(db, session_id))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="session_expired")
    except BufferNotReadyError:
        raise HTTPException(status_code=409, detail="buffer_not_ready")


@router.get("/sessions/{session_id}/report", response_model=schemas.SessionReport)
def get_speed_report(session_id: str, db: Session = Depends(get_db)):
    """Authoritative per-puzzle report rebuilt from stored attempts."""
    try:
        data = sessions.report(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="session_not_found")
    return schemas.SessionReport(
        session=schemas.SessionSummary(**{k: v for k, v in data.items() if k != "entries"}),
        entries=[schemas.ReportEntry(**e) for e in data["entries"]],
    )


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
    except SessionNotActiveError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
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
