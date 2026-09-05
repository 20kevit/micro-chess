"""Piece Recognition speed sessions: authoritative 60-second clock.

The frontend runs a visible countdown for UX, but ONLY this service decides
whether a submission counts: ``submit`` compares server time against the
stored ``ends_at`` and rejects late answers. Scoring reuses the standard
``progress.service.submit_attempt`` (mode=practice) plus
``scoring_engine.score_for`` — no separate scoring system.

Session lifecycle: active -> finished (client ends early / time runs out and
the summary is read) or active -> expired (a call arrives after the clock).
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.piece_recognition import generator
from app.modules.piece_recognition.models import PieceSpeedSession
from app.modules.piece_recognition.validator import SLUG
from app.modules.progress import service as attempt_service
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptMode

SPEED_DURATION_S = 60


class SessionNotFoundError(ValueError):
    pass


class SessionExpiredError(ValueError):
    pass


class PuzzleNotInSessionError(ValueError):
    pass


class PuzzleAlreadyAnsweredError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _expire_if_needed(db: Session, session: PieceSpeedSession) -> PieceSpeedSession:
    if session.status == "active" and _now() >= session.ends_at:
        session.status = "expired"
        db.commit()
        db.refresh(session)
    return session


def start_session(
    db: Session,
    *,
    user_id: int | None = None,
    duration_s: int | None = None,
) -> PieceSpeedSession:
    duration = duration_s if duration_s else SPEED_DURATION_S
    duration = max(15, min(300, int(duration)))
    started = _now()
    session = PieceSpeedSession(
        id=uuid.uuid4().hex,
        exercise_slug=SLUG,
        user_id=user_id,
        status="active",
        duration_s=duration,
        started_at=started,
        ends_at=started + timedelta(seconds=duration),
        puzzle_ids=[],
        attempt_ids=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> PieceSpeedSession:
    session = db.get(PieceSpeedSession, session_id)
    if session is None:
        raise SessionNotFoundError("session_not_found")
    return _expire_if_needed(db, session)


def _require_active(db: Session, session_id: str) -> PieceSpeedSession:
    session = get_session(db, session_id)
    if session.status != "active":
        raise SessionExpiredError("session_expired")
    return session


def issue_puzzle(
    db: Session,
    session_id: str,
    rng: random.Random | None = None,
) -> Puzzle:
    session = _require_active(db, session_id)
    puzzle = generator.create_puzzle(db, rng)
    ids = list(session.puzzle_ids or [])
    ids.append(puzzle.id)
    session.puzzle_ids = ids
    db.commit()
    db.refresh(session)
    return puzzle


def issue_practice_puzzle(db: Session, rng: random.Random | None = None) -> Puzzle:
    """Next random puzzle for untimed Practice Mode (no session)."""
    return generator.create_puzzle(db, rng)


def submit(
    db: Session,
    session_id: str,
    *,
    user_id: int | None,
    puzzle_id: int,
    answer: dict[str, Any],
    hints_used: list[str] | None = None,
    started_at: datetime | None = None,
):
    """Submit one session answer. Authoritative: late answers are rejected."""
    session = _require_active(db, session_id)
    if puzzle_id not in (session.puzzle_ids or []):
        raise PuzzleNotInSessionError("puzzle_not_in_session")
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None or not puzzle.is_published or puzzle.is_archived:
        raise PuzzleNotInSessionError("puzzle_not_available")
    # Client-supplied FEN/target/solution metadata is ignored: validation
    # always runs against the stored server-side answer_json.
    safe_answer = {"selected_squares": answer.get("selected_squares", [])} if isinstance(answer, dict) else {}
    attempt, feedback_key, detail = attempt_service.submit_attempt(
        db,
        user_id=user_id if user_id is not None else session.user_id,
        puzzle_id=puzzle.id,
        answer=safe_answer,
        mode=AttemptMode.PRACTICE,
        hints_used=hints_used,
        started_at=started_at,
    )
    session.attempt_ids = list(session.attempt_ids or []) + [attempt.id]
    session.attempted_count = (session.attempted_count or 0) + 1
    if attempt.result == "correct":
        session.correct_count = (session.correct_count or 0) + 1
    elif attempt.result == "partial":
        session.partial_count = (session.partial_count or 0) + 1
    else:
        session.wrong_count = (session.wrong_count or 0) + 1
    session.score = (session.score or 0.0) + (attempt.score or 0.0)
    db.commit()
    db.refresh(session)
    return attempt, feedback_key, detail, session


def finish(db: Session, session_id: str) -> PieceSpeedSession:
    session = get_session(db, session_id)
    if session.status == "active":
        session.status = "finished"
        db.commit()
        db.refresh(session)
    return session


def summary(session: PieceSpeedSession) -> dict[str, Any]:
    remaining_ms = max(0, int((session.ends_at - _now()).total_seconds() * 1000))
    return {
        "session_id": session.id,
        "exercise_slug": session.exercise_slug,
        "status": session.status,
        "duration_s": session.duration_s,
        "started_at": session.started_at,
        "expires_at": session.ends_at,
        "remaining_ms": remaining_ms,
        "attempted": session.attempted_count or 0,
        "correct": session.correct_count or 0,
        "partial": session.partial_count or 0,
        "wrong": session.wrong_count or 0,
        "score": session.score or 0.0,
    }
