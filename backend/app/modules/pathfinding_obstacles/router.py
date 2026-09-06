"""Pathfinding-with-obstacles routes: step oracle + practice + speed.

Thin wiring only; transitions/scoring/clock live in transitions/
validator/scoring, generator/sessions and the shared progress service.
The authoritative answer (optimal move count, BFS path) is never exposed:
``next`` and session endpoints return ``PuzzleOut`` (no ``answer_json``).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional, get_db
from app.modules.pathfinding_obstacles import schemas, sessions
from app.modules.pathfinding_obstacles import transitions as tr
from app.modules.pathfinding_obstacles.sessions import (
    BufferNotReadyError,
    PuzzleNotInSessionError,
    SessionExpiredError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from app.modules.pathfinding_obstacles.validator import SLUG, apply_step, mover_kind
from app.modules.progress.schemas import AttemptOut
from app.modules.puzzles.models import Puzzle
from app.modules.puzzles.schemas import PuzzleOut
from app.modules.rule_engine.base import normalize_square

router = APIRouter(prefix="/pathfinding-obstacles", tags=["pathfinding-obstacles"])


def _to_out(session: sessions.ObstaclePathfindingSpeedSession) -> schemas.SessionOut:
    data = sessions.summary(session)
    return schemas.SessionOut(**data)


def _to_summary(session: sessions.ObstaclePathfindingSpeedSession) -> schemas.SessionSummary:
    return schemas.SessionSummary(**sessions.summary(session))


def _live_state(puzzle: Puzzle, fen: str) -> tr.State | None:
    """Rebuild the live state: placement from the client FEN, kind/target
    from the server-stored answer. None when inconsistent."""
    answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
    try:
        kind = mover_kind(answer)
    except ValueError:
        return None
    target = normalize_square(answer.get("target"))
    if target is None:
        return None
    stored_enemies = answer.get("enemies")
    hint: dict[str, str] | None = None
    if isinstance(stored_enemies, list):
        hint = {}
        for entry in stored_enemies:
            if isinstance(entry, dict) and isinstance(entry.get("square"), str):
                sq = normalize_square(entry.get("square"))
                raw_kind = entry.get("kind")
                kind_name = raw_kind.strip().lower() if isinstance(raw_kind, str) else ""
                if sq and kind_name in tr.ALLOWED_ENEMY_KINDS:
                    hint[sq] = kind_name
    try:
        return tr.state_from_fen(fen, white_kind=kind, target=target, enemies_hint=hint)
    except ValueError:
        return None


def _reject(fen: str, selected_at: str) -> schemas.StepOut:
    return schemas.StepOut(
        ok=False,
        fen=fen,
        selected_at=selected_at,
        reached=False,
        captured=None,
        message_key="pathfinding.invalid",
    )


@router.post("/step", response_model=schemas.StepOut)
def validate_step(body: schemas.StepIn, db: Session = Depends(get_db)):
    puzzle: Puzzle | None = db.get(Puzzle, body.puzzle_id)
    if (
        puzzle is None
        or not puzzle.is_published
        or puzzle.is_archived
        or puzzle.exercise_slug != SLUG
    ):
        raise HTTPException(status_code=404, detail="puzzle_not_available")

    answer = puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {}
    target = normalize_square(answer.get("target"))
    selected_at = normalize_square(body.selected_at)
    origin = normalize_square(body.from_square)
    dest = normalize_square(body.to_square)
    if selected_at is None or origin is None or dest is None or target is None:
        return _reject(body.fen, body.selected_at)
    if origin != selected_at:
        # Only the selected piece moves; anything else is not a step.
        return _reject(body.fen, body.selected_at)
    state = _live_state(puzzle, body.fen)
    if state is None:
        return _reject(body.fen, body.selected_at)
    if state.white_square != origin:
        # Client board disagrees with the selected piece: not a step.
        return _reject(body.fen, body.selected_at)
    nxt = apply_step(state, origin, dest)
    if nxt is None:
        return _reject(body.fen, body.selected_at)
    captured = dest if len(nxt.enemies) < len(state.enemies) else None
    return schemas.StepOut(
        ok=True,
        fen=tr.fen_for_state(nxt),
        selected_at=dest,
        reached=dest == target,
        captured=captured,
        message_key="",
    )


@router.post("/next", response_model=PuzzleOut)
def next_practice_puzzle(
    body: schemas.NextPracticeIn | None = None, db: Session = Depends(get_db)
):
    """Issue one fresh solved puzzle for untimed Practice Mode."""
    from app.modules.pathfinding_obstacles import generator

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
