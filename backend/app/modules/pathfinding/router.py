"""Pathfinding routes: step assistance + practice next + speed sessions.

Thin wiring only; movement/scoring/clock live in moves/validator/scoring,
generator/sessions and the shared progress service. The authoritative
answer (optimal move count, BFS path) is never exposed: ``next`` and
session endpoints return ``PuzzleOut`` (no ``answer_json``).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional, get_db
from app.modules.pathfinding import schemas, sessions
from app.modules.pathfinding import moves as move_geom
from app.modules.pathfinding.sessions import (
    BufferNotReadyError,
    PuzzleNotInSessionError,
    SessionExpiredError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from app.modules.pathfinding.validator import SLUG, apply_step, mover_kind
from app.modules.progress.schemas import AttemptOut
from app.modules.puzzles.models import Puzzle
from app.modules.puzzles.schemas import PuzzleOut
from app.modules.rule_engine.base import normalize_square

router = APIRouter(prefix="/pathfinding", tags=["pathfinding"])


def _to_out(session: sessions.PathfindingSpeedSession) -> schemas.SessionOut:
    data = sessions.summary(session)
    return schemas.SessionOut(**data)


def _to_summary(session: sessions.PathfindingSpeedSession) -> schemas.SessionSummary:
    return schemas.SessionSummary(**sessions.summary(session))


def _move_piece_in_fen(fen: str, kind: str, origin: str, dest: str) -> str | None:
    """Move the single white piece inside the FEN placement. None when bad."""
    letter = move_geom.PIECE_LETTER.get(kind)
    if letter is None:
        return None
    parts = fen.split(" ")
    rows = parts[0].split("/") if parts else []
    if len(rows) != 8:
        return None
    board: list[list[str | None]] = []
    for row in rows:
        cells: list[str | None] = []
        for ch in row:
            if ch.isdigit():
                cells.extend([None] * int(ch))
            elif ch.isalpha():
                cells.append(ch)
            else:
                return None
        if len(cells) != 8:
            return None
        board.append(cells)
    try:
        fx, fy = "abcdefgh".index(origin[0]), int(origin[1:]) - 1
        tx, ty = "abcdefgh".index(dest[0]), int(dest[1:]) - 1
    except (ValueError, IndexError):
        return None
    from_row, to_row = 8 - 1 - fy, 8 - 1 - ty
    if board[from_row][fx] != letter or board[to_row][tx] is not None:
        # Only the selected white piece moves, onto an empty square
        # (no captures exist in Exercise 6).
        return None
    board[from_row][fx] = None
    board[to_row][tx] = letter
    out_rows: list[str] = []
    for cells in board:
        row, empty = "", 0
        for cell in cells:
            if cell is None:
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += cell
        if empty:
            row += str(empty)
        out_rows.append(row)
    parts[0] = "/".join(out_rows)
    return " ".join(parts)


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
    if origin == target:
        # The star is already reached: the puzzle is complete and no
        # further moves are accepted (the client auto-submits on arrival).
        return _reject(body.fen, body.selected_at)
    try:
        kind = mover_kind(answer)
    except ValueError:
        return _reject(body.fen, body.selected_at)
    try:
        checked = apply_step(kind, origin, dest)
    except ValueError:
        return _reject(body.fen, body.selected_at)
    if checked is None:
        return _reject(body.fen, body.selected_at)
    new_fen = _move_piece_in_fen(body.fen, kind, origin, dest)
    if new_fen is None:
        return _reject(body.fen, body.selected_at)
    return schemas.StepOut(
        ok=True,
        fen=new_fen,
        selected_at=dest,
        reached=dest == target,
        captured=None,
        message_key="",
    )


@router.post("/next", response_model=PuzzleOut)
def next_practice_puzzle(
    body: schemas.NextPracticeIn | None = None, db: Session = Depends(get_db)
):
    """Issue one fresh random puzzle for untimed Practice Mode."""
    from app.modules.pathfinding import generator

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
