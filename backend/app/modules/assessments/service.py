"""Assessment application service (P6).

Business rules live here; there is no router in this phase (creation
and closure happen through the service layer). Every decision combines
the same authorization shape as the relationship layer:

```text
party membership (student or creating coach, checked here per request)
+
active coach relationship for third-party creators (checked here)
```

Lifecycle is exactly ``active -> completed | cancelled``. Terminal
states never reopen, closing is idempotent, and closing never touches
attempts, ratings, XP, evidence, or skill state.

A ``ValueError`` carries the machine-readable error code.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.admin.service import record_audit
from app.modules.assessments.models import (
    ASSESSMENT_ACTIVE,
    ASSESSMENT_CANCELLED,
    ASSESSMENT_COMPLETED,
    ASSESSMENT_STATUSES,
    Assessment,
)
from app.modules.relationships import service as relationship_service
from app.modules.relationships.models import (
    ASSIGNMENT_ASSIGNED,
    KIND_COACH,
    Assignment,
)
from app.modules.users.models import User


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_assessment(
    db: Session,
    *,
    creator: User,
    student_id: int,
    assignment_id: int | None = None,
    note: str = "",
) -> Assessment:
    """Open an assessment session for one student.

    The creator is either the student themselves (self-assessment) or
    a coach holding an ACTIVE coach relationship to that student.
    Anyone else (unrelated coaches, parents, other students) is
    rejected. Revoked relationships immediately block new sessions.

    When ``assignment_id`` is given, the session executes that direct
    assignment: it must belong to the same student, still be
    ``assigned``, and -- for coach creators -- be the creator's own
    assignment. System recommendations are never accepted here (they
    live in ``adaptive_recommendations`` and stay unimplemented).
    """
    student = db.get(User, int(student_id))
    if student is None or not student.is_active or not creator.is_active:
        raise ValueError("unknown_student")
    is_self = creator.id == student.id
    if not is_self:
        if not relationship_service.has_role(db, creator.id, "COACH"):
            raise ValueError("assessment_forbidden")
        link = relationship_service.active_link(
            db, kind=KIND_COACH, mentor_id=creator.id, student_id=student.id
        )
        if link is None:
            raise ValueError("assessment_forbidden")
    assignment: Assignment | None = None
    if assignment_id is not None:
        assignment = db.get(Assignment, int(assignment_id))
        if assignment is None:
            raise ValueError("unknown_assignment")
        if (
            assignment.student_user_id != student.id
            or assignment.status != ASSIGNMENT_ASSIGNED
        ):
            raise ValueError("assessment_forbidden")
        if not is_self and assignment.coach_user_id != creator.id:
            raise ValueError("assessment_forbidden")
    row = Assessment(
        student_user_id=student.id,
        created_by_user_id=creator.id,
        assignment_id=assignment.id if assignment is not None else None,
        note=str(note or "").strip()[:500],
        status=ASSESSMENT_ACTIVE,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=creator.id,
        action="assessments.create",
        target_type="assessment",
        target_id=row.id,
        metadata={"student_user_id": student.id, "assignment_id": row.assignment_id},
    )
    return row


def get_assessment(db: Session, user: User, assessment_id: int) -> Assessment | None:
    """One assessment, or None when missing or the caller is not a party.

    Parties are the assessed student and the creator. Parents, other
    coaches, and other students see nothing (callers map None to 404).
    """
    row = db.get(Assessment, int(assessment_id))
    if row is None:
        return None
    if user.id not in (row.student_user_id, row.created_by_user_id):
        return None
    return row


def list_for_student(
    db: Session, student: User, *, page: int = 1, page_size: int = 50
) -> list[Assessment]:
    return (
        db.query(Assessment)
        .filter(Assessment.student_user_id == student.id)
        .order_by(Assessment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def list_created_by(
    db: Session, creator: User, *, page: int = 1, page_size: int = 50
) -> list[Assessment]:
    return (
        db.query(Assessment)
        .filter(Assessment.created_by_user_id == creator.id)
        .order_by(Assessment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def _close(
    db: Session, *, actor: User, assessment_id: int, status: str
) -> tuple[Assessment, bool] | None:
    clean = str(status or "").strip().lower()
    if clean not in ASSESSMENT_STATUSES:
        raise ValueError("invalid_status")
    row = get_assessment(db, actor, assessment_id)
    if row is None:
        return None
    if row.status == clean:
        return row, False
    if row.status != ASSESSMENT_ACTIVE:
        raise ValueError("invalid_transition")
    is_student = actor.id == row.student_user_id
    is_creator = actor.id == row.created_by_user_id
    if not (is_student or is_creator):
        raise ValueError("assessment_forbidden")  # pragma: no cover - get_assessment already scopes parties
    if clean == ASSESSMENT_COMPLETED:
        row.status = ASSESSMENT_COMPLETED
        row.completed_at = _utcnow()
    elif clean == ASSESSMENT_CANCELLED:
        row.status = ASSESSMENT_CANCELLED
    else:  # pragma: no cover - active->active handled by same-state return above
        raise ValueError("invalid_transition")
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=actor.id,
        action="assessments.update",
        target_type="assessment",
        target_id=row.id,
        metadata={"status": clean},
    )
    return row, True


def complete_assessment(
    db: Session, *, actor: User, assessment_id: int
) -> tuple[Assessment, bool] | None:
    """Close a session as completed. Student or creator; terminal states never reopen."""
    return _close(db, actor=actor, assessment_id=assessment_id, status=ASSESSMENT_COMPLETED)


def cancel_assessment(
    db: Session, *, actor: User, assessment_id: int
) -> tuple[Assessment, bool] | None:
    """Close a session as cancelled. Student or creator; terminal states never reopen."""
    return _close(db, actor=actor, assessment_id=assessment_id, status=ASSESSMENT_CANCELLED)


def resolve_for_attempt(db: Session, *, user_id: int, assessment_id: int) -> Assessment:
    """Return the open session an attempt may attach to.

    Raises ``assessment_not_available`` when the session is missing,
    belongs to another student, or is no longer active. Attempt history
    is append-only: closing a session never detaches its attempts.
    """
    row = db.get(Assessment, int(assessment_id))
    if row is None or row.student_user_id != int(user_id) or row.status != ASSESSMENT_ACTIVE:
        raise ValueError("assessment_not_available")
    return row


__all__ = [
    "cancel_assessment",
    "complete_assessment",
    "create_assessment",
    "get_assessment",
    "list_created_by",
    "list_for_student",
    "resolve_for_attempt",
]
