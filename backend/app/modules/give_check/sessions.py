"""Giving Check speed sessions: prepared buffer + authoritative clock.

Lifecycle: ``preparing`` -> ``active`` -> ``finished``/``expired``.

- ``preparing``: the client preloads at least ``MIN_START_BUFFER`` (20)
  puzzles via ``prepare_puzzles``. No clock runs; submissions are refused.
- ``begin_session`` starts the 60s clock (requires the minimum buffer) and
  flips the session to ``active``. Only then do ``next``/``submit`` work.
- The frontend runs a visible countdown for UX, but ONLY this service
  decides whether a submission counts: ``submit`` compares server time
  against the stored ``ends_at`` and rejects late answers.
- Scoring reuses the standard ``progress.service.submit_attempt``
  (mode=practice) plus the registered exercise scorer — no separate
  scoring system. Per-answer rows live in ``attempts``; this table only
  aggregates, so the final report is rebuilt from stored attempts.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.progress import service as attempt_service
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptMode
from app.modules.puzzles import service as puzzle_service
from app.modules.give_check.models import GivingCheckSpeedSession
from app.modules.give_check.validator import SLUG

SPEED_DURATION_S = 60
# Minimum preloaded puzzles before the clock may start. The client keeps
# refilling in the background, so fast solvers never wait mid-session.
MIN_START_BUFFER = 20
# Per-call cap for buffer preparation (keeps one request bounded).
MAX_PREPARE_COUNT = 60


class SessionNotFoundError(ValueError):
    pass


class SessionExpiredError(ValueError):
    pass


class SessionNotActiveError(ValueError):
    pass


class BufferNotReadyError(ValueError):
    pass


class PuzzleNotInSessionError(ValueError):
    pass


class PuzzleAlreadyAnsweredError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _expire_if_needed(db: Session, session: GivingCheckSpeedSession) -> GivingCheckSpeedSession:
    if (
        session.status == "active"
        and session.ends_at is not None
        and _now() >= session.ends_at
    ):
        session.status = "expired"
        db.commit()
        db.refresh(session)
    return session


def start_session(
    db: Session,
    *,
    user_id: int | None = None,
    duration_s: int | None = None,
) -> GivingCheckSpeedSession:
    duration = duration_s if duration_s else SPEED_DURATION_S
    duration = max(15, min(300, int(duration)))
    started = _now()
    session = GivingCheckSpeedSession(
        id=uuid.uuid4().hex,
        exercise_slug=SLUG,
        user_id=user_id,
        status="preparing",
        duration_s=duration,
        started_at=started,
        ends_at=None,
        puzzle_ids=[],
        attempt_ids=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> GivingCheckSpeedSession:
    session = db.get(GivingCheckSpeedSession, session_id)
    if session is None:
        raise SessionNotFoundError("session_not_found")
    return _expire_if_needed(db, session)


def _require_active(db: Session, session_id: str) -> GivingCheckSpeedSession:
    session = get_session(db, session_id)
    if session.status == "preparing":
        raise SessionNotActiveError("session_not_started")
    if session.status != "active":
        raise SessionExpiredError("session_expired")
    return session


def _require_preparable(db: Session, session_id: str) -> GivingCheckSpeedSession:
    session = get_session(db, session_id)
    if session.status not in ("preparing", "active"):
        raise SessionExpiredError("session_expired")
    return session


def begin_session(db: Session, session_id: str) -> GivingCheckSpeedSession:
    """Start the clock. Requires the minimum preloaded buffer; the 60s
    never include preparation time."""
    session = get_session(db, session_id)
    if session.status == "active":
        return session
    if session.status != "preparing":
        raise SessionExpiredError("session_expired")
    if len(session.puzzle_ids or []) < MIN_START_BUFFER:
        raise BufferNotReadyError("buffer_not_ready")
    started = _now()
    session.started_at = started
    session.ends_at = started + timedelta(seconds=session.duration_s or SPEED_DURATION_S)
    session.status = "active"
    db.commit()
    db.refresh(session)
    return session


def _attach_puzzles(
    db: Session,
    session: GivingCheckSpeedSession,
    count: int,
    rng: random.Random | None = None,
) -> list[Puzzle]:
    made: list[Puzzle] = []
    # Exclude already-buffered ids so one buffer stays duplicate-free
    # (best-effort; the generator re-rolls bounded times).
    excluded = set(session.puzzle_ids or [])
    for _ in range(max(0, count)):
        puzzle = puzzle_service.player_puzzle(db, SLUG, exclude_ids=excluded)
        excluded.add(puzzle.id)
        made.append(puzzle)
    ids = list(session.puzzle_ids or []) + [p.id for p in made]
    session.puzzle_ids = ids
    db.commit()
    db.refresh(session)
    return made


def prepare_puzzles(
    db: Session,
    session_id: str,
    count: int = MIN_START_BUFFER,
    rng: random.Random | None = None,
) -> list[Puzzle]:
    """Generate ``count`` puzzles into the session buffer. Allowed while
    ``preparing`` (initial buffer) and while ``active`` (background refill).
    Returns the created puzzles (public fields only leave the API)."""
    session = _require_preparable(db, session_id)
    return _attach_puzzles(db, session, max(1, min(MAX_PREPARE_COUNT, int(count or 0))), rng)


def issue_puzzle(
    db: Session,
    session_id: str,
    rng: random.Random | None = None,
) -> Puzzle:
    session = _require_preparable(db, session_id)
    puzzle = puzzle_service.player_puzzle(db, SLUG)
    ids = list(session.puzzle_ids or [])
    ids.append(puzzle.id)
    session.puzzle_ids = ids
    db.commit()
    db.refresh(session)
    return puzzle


def issue_practice_puzzle(db: Session, rng: random.Random | None = None) -> Puzzle:
    """Next random puzzle for untimed Practice Mode (no session)."""
    return puzzle_service.player_puzzle(db, SLUG)


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
    try:
        puzzle = puzzle_service.require_visible_puzzle(db, puzzle_id, SLUG)
    except puzzle_service.PlayerPuzzleUnavailableError as exc:
        raise PuzzleNotInSessionError(str(exc)) from exc
    # Client-supplied FEN/target/solution metadata is ignored: validation
    # always runs against the stored server-side answer_json.
    safe_answer = {"moves": answer.get("moves", [])} if isinstance(answer, dict) else {}
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


def finish(db: Session, session_id: str) -> GivingCheckSpeedSession:
    session = get_session(db, session_id)
    if session.status in ("preparing", "active"):
        session.status = "finished"
        db.commit()
        db.refresh(session)
    return session


def summary(session: GivingCheckSpeedSession) -> dict[str, Any]:
    if session.ends_at is None:
        remaining_ms = (session.duration_s or SPEED_DURATION_S) * 1000
        expires_at = None
    else:
        remaining_ms = max(0, int((session.ends_at - _now()).total_seconds() * 1000))
        expires_at = session.ends_at
    return {
        "session_id": session.id,
        "exercise_slug": session.exercise_slug,
        "status": session.status,
        "duration_s": session.duration_s,
        "started_at": session.started_at,
        "expires_at": expires_at,
        "remaining_ms": remaining_ms,
        "buffered": len(session.puzzle_ids or []),
        "attempted": session.attempted_count or 0,
        "correct": session.correct_count or 0,
        "partial": session.partial_count or 0,
        "wrong": session.wrong_count or 0,
        "score": session.score or 0.0,
    }


def report(db: Session, session_id: str) -> dict[str, Any]:
    """Authoritative per-puzzle report rebuilt from stored attempts, so a
    refresh or UI glitch can never fabricate or lose results.

    Per-move detail is re-derived server-side by re-running the exercise
    validator over the stored puzzle answer + stored user answer (never
    trusted from any client payload).
    """
    from app.modules.exercises import registry
    from app.modules.progress.models import Attempt

    session = get_session(db, session_id)
    data = summary(session)
    attempt_ids = list(session.attempt_ids or [])
    entries: list[dict[str, Any]] = []
    if attempt_ids:
        attempts = (
            db.query(Attempt).filter(Attempt.id.in_(attempt_ids)).order_by(Attempt.id).all()
        )
        puzzles = {
            p.id: p
            for p in db.query(Puzzle).filter(
                Puzzle.id.in_([a.puzzle_id for a in attempts])
            )
        }
        for attempt in attempts:
            puzzle = puzzles.get(attempt.puzzle_id)
            if puzzle is not None:
                detail = dict(
                    registry.validate_answer(
                        attempt.exercise_slug,
                        puzzle.answer_json if isinstance(puzzle.answer_json, dict) else {},
                        attempt.answer_json if isinstance(attempt.answer_json, dict) else {},
                    ).detail
                )
            else:  # pragma: no cover - defensive; puzzles are never deleted
                detail = {"correct": [], "missed": [], "wrong": []}
            entries.append(
                {
                    "attempt_id": attempt.id,
                    "puzzle_id": attempt.puzzle_id,
                    "prompt_fa": puzzle.prompt_fa if puzzle else "",
                    "fen": puzzle.fen if puzzle else None,
                    "result": attempt.result,
                    "score": attempt.score,
                    "correct": list(detail.get("correct", [])),
                    "missed": list(detail.get("missed", [])),
                    "wrong": list(detail.get("wrong", [])),
                    "created_at": attempt.created_at,
                }
            )
    data["entries"] = entries
    return data
