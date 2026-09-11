"""Relationship application service (Phase 9).

Business rules live here; routers stay thin. Every decision combines:

```text
capability (enforced by the router dependency)
+
active relationship (checked here, per request, from the database)
+
object authorization (party membership + kind filtering, checked here)
+
privacy rules (response shapes limited to explicitly permitted fields)
```

Lifecycle is exactly ``pending -> active -> revoked``. Declining a
pending invitation revokes it (no separate rejected state; history is
preserved either way). Revoked rows never authorize again, and a new
invitation after revocation creates a new row (history preserved).

A ``ValueError`` carries the machine-readable error code; routers map
codes to HTTP status.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.admin.service import record_audit
from app.modules.player.models import PlayerProfile
from app.modules.relationships.models import (
    ASSIGNMENT_CANCELLED,
    ASSIGNMENT_COMPLETED,
    ASSIGNMENT_STATUSES,
    KIND_COACH,
    KIND_PARENT,
    KINDS,
    STATUSES,
    STATUS_ACTIVE,
    STATUS_PENDING,
    STATUS_REVOKED,
    Assignment,
    Relationship,
)
from app.modules.users.models import User, UserRole


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- small lookups ------------------------------------------------------------


def normalize_username(value: object) -> str:
    return str(value or "").strip().lower()


def find_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == normalize_username(username)).first()


def has_role(db: Session, user_id: int, role: str) -> bool:
    return (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.role == role)
        .first()
        is not None
    )


def display_name_for(db: Session, user: User) -> str:
    profile = db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id).first()
    if profile is not None and (profile.display_name or "").strip():
        return profile.display_name
    if (user.display_name or "").strip():
        return user.display_name
    return user.username or ""


def _mentor_role_for_kind(kind: str) -> str:
    return "COACH" if kind == KIND_COACH else "PARENT"


# --- creation -----------------------------------------------------------------


def create_relationship(db: Session, *, actor: User, kind: str, other_username: str) -> Relationship:
    """Create a PENDING invitation between the actor and the other account.

    The invitation grants nothing until the other party accepts. Either
    direction is allowed (mentor invites student, or student invites
    mentor); the acceptor must always be the non-creating party.
    """
    clean_kind = str(kind or "").strip().lower()
    if clean_kind not in KINDS:
        raise ValueError("invalid_kind")
    other = find_user_by_username(db, other_username)
    if other is None:
        raise ValueError("unknown_user")
    if other.id == actor.id:
        raise ValueError("self_relationship")
    mentor_role = _mentor_role_for_kind(clean_kind)
    actor_is_mentor = has_role(db, actor.id, mentor_role)
    other_is_mentor = has_role(db, other.id, mentor_role)
    if actor_is_mentor and not other_is_mentor:
        mentor_id, student_id = actor.id, other.id
    elif other_is_mentor and not actor_is_mentor:
        mentor_id, student_id = other.id, actor.id
    elif actor_is_mentor and other_is_mentor:
        # Both hold the mentor role (e.g. two coaches): the initiator is
        # the mentor, the other party the student. Role combination stays
        # explicit; nothing is inferred from names or profiles.
        mentor_id, student_id = actor.id, other.id
    else:
        raise ValueError("invalid_role_combination")
    mentor = db.get(User, mentor_id)
    student = db.get(User, student_id)
    if mentor is None or student is None or not mentor.is_active or not student.is_active:
        raise ValueError("account_inactive")
    existing = (
        db.query(Relationship)
        .filter(
            Relationship.kind == clean_kind,
            Relationship.mentor_user_id == mentor_id,
            Relationship.student_user_id == student_id,
            Relationship.status.in_([STATUS_PENDING, STATUS_ACTIVE]),
        )
        .first()
    )
    if existing is not None:
        raise ValueError("relationship_exists")
    row = Relationship(
        kind=clean_kind,
        mentor_user_id=mentor_id,
        student_user_id=student_id,
        status=STATUS_PENDING,
        created_by_user_id=actor.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=actor.id,
        action="relationships.create",
        target_type="relationship",
        target_id=row.id,
        metadata={"kind": clean_kind, "mentor_user_id": mentor_id, "student_user_id": student_id},
    )
    return row


# --- reads (own scope only) ----------------------------------------------------


def list_relationships(
    db: Session,
    user: User,
    *,
    kind: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Relationship]:
    """Relationships the caller belongs to. Database-side filtering."""
    if kind is not None and kind not in KINDS:
        raise ValueError("invalid_kind")
    if status is not None and status not in STATUSES:
        raise ValueError("invalid_status")
    query = db.query(Relationship).filter(
        (Relationship.mentor_user_id == user.id) | (Relationship.student_user_id == user.id)
    )
    if kind is not None:
        query = query.filter(Relationship.kind == kind)
    if status is not None:
        query = query.filter(Relationship.status == status)
    return (
        query.order_by(Relationship.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def get_relationship(db: Session, user: User, relationship_id: int) -> Relationship | None:
    """One relationship, or None when missing or the caller is not a party."""
    row = db.get(Relationship, relationship_id)
    if row is None:
        return None
    if user.id not in (row.mentor_user_id, row.student_user_id):
        return None
    return row


# --- transitions ----------------------------------------------------------------


def accept_relationship(db: Session, *, actor: User, relationship_id: int) -> tuple[Relationship, bool] | None:
    """Accept a pending invitation. Only the non-creating party may accept.

    Idempotent: accepting an already-active relationship returns it
    unchanged. Returns None when missing or the actor is not a party.
    """
    row = get_relationship(db, actor, relationship_id)
    if row is None:
        return None
    if row.status == STATUS_ACTIVE:
        return row, False
    if row.status != STATUS_PENDING:
        raise ValueError("invalid_transition")
    if row.created_by_user_id == actor.id:
        raise ValueError("accept_forbidden")
    mentor = db.get(User, row.mentor_user_id)
    student = db.get(User, row.student_user_id)
    if mentor is None or student is None or not mentor.is_active or not student.is_active:
        raise ValueError("account_inactive")
    row.status = STATUS_ACTIVE
    row.accepted_at = _utcnow()
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=actor.id,
        action="relationships.accept",
        target_type="relationship",
        target_id=row.id,
        metadata={"kind": row.kind},
    )
    return row, True


def revoke_relationship(db: Session, *, actor: User, relationship_id: int) -> tuple[Relationship, bool] | None:
    """Revoke a pending or active relationship. Either party may revoke.

    Idempotent: revoking an already-revoked relationship returns it
    unchanged. Returns None when missing or the actor is not a party.
    """
    row = get_relationship(db, actor, relationship_id)
    if row is None:
        return None
    if row.status == STATUS_REVOKED:
        return row, False
    if row.status not in (STATUS_PENDING, STATUS_ACTIVE):
        raise ValueError("invalid_transition")
    row.status = STATUS_REVOKED
    row.revoked_at = _utcnow()
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=actor.id,
        action="relationships.revoke",
        target_type="relationship",
        target_id=row.id,
        metadata={"kind": row.kind},
    )
    return row, True


# --- relationship-aware authorization ------------------------------------------


def active_link(db: Session, *, kind: str, mentor_id: int, student_id: int) -> Relationship | None:
    """The authorizing edge, or None when no ACTIVE relationship covers it."""
    return (
        db.query(Relationship)
        .filter(
            Relationship.kind == kind,
            Relationship.mentor_user_id == mentor_id,
            Relationship.student_user_id == student_id,
            Relationship.status == STATUS_ACTIVE,
        )
        .first()
    )


def assert_authorized_student(db: Session, *, kind: str, mentor: User, student_id: int) -> User | None:
    """Return the student when the mentor holds an active relationship.

    Returns None when: no active relationship, either account inactive,
    or the student does not exist. Callers map None to 404 so related
    and unrelated students are indistinguishable to unauthorized callers.
    """
    student = db.get(User, student_id)
    if student is None or not student.is_active or not mentor.is_active:
        return None
    link = active_link(db, kind=kind, mentor_id=mentor.id, student_id=student_id)
    if link is None:
        return None
    return student


def list_related_students(
    db: Session,
    mentor: User,
    *,
    kind: str,
    page: int = 1,
    page_size: int = 50,
) -> list[tuple[Relationship, User]]:
    """Active students for one mentor. Database-side join, no Python filter."""
    rows = (
        db.query(Relationship, User)
        .join(User, User.id == Relationship.student_user_id)
        .filter(
            Relationship.kind == kind,
            Relationship.mentor_user_id == mentor.id,
            Relationship.status == STATUS_ACTIVE,
            User.is_active == True,  # noqa: E712
        )
        .order_by(Relationship.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [(rel, student) for rel, student in rows]


# --- assignments (foundation) ----------------------------------------------------


def _parse_due_at(raw: str | None) -> datetime | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        moment = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError("due_at_invalid")
    return moment.replace(tzinfo=None)


def create_assignment(
    db: Session,
    *,
    coach: User,
    student_id: int,
    exercise_slug: str,
    note: str = "",
    due_at: str | None = None,
) -> Assignment:
    """Assign an exercise to an actively-related student.

    Requires an ACTIVE coach relationship covering this exact pair.
    Revoked relationships immediately block new assignments.
    """
    from app.modules.player import service as player_service

    slug = str(exercise_slug or "").strip()
    if not slug:
        raise ValueError("unknown_exercise")
    if not player_service.is_known_exercise(db, slug):
        raise ValueError("unknown_exercise")
    student = assert_authorized_student(db, kind=KIND_COACH, mentor=coach, student_id=student_id)
    if student is None:
        raise ValueError("no_active_relationship")
    link = active_link(db, kind=KIND_COACH, mentor_id=coach.id, student_id=student_id)
    assert link is not None
    clean_note = str(note or "").strip()[:500]
    row = Assignment(
        coach_user_id=coach.id,
        student_user_id=student_id,
        relationship_id=link.id,
        exercise_slug=slug,
        note=clean_note,
        due_at=_parse_due_at(due_at),
        status="assigned",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=coach.id,
        action="assignments.create",
        target_type="assignment",
        target_id=row.id,
        metadata={"student_user_id": student_id, "exercise_slug": slug},
    )
    return row


def get_assignment(db: Session, user: User, assignment_id: int) -> Assignment | None:
    """One assignment, or None when missing or the caller is not a party."""
    row = db.get(Assignment, assignment_id)
    if row is None:
        return None
    if user.id not in (row.coach_user_id, row.student_user_id):
        return None
    return row


def list_assignments_for_coach(
    db: Session, coach: User, *, student_id: int | None = None, page: int = 1, page_size: int = 50
) -> list[Assignment]:
    query = db.query(Assignment).filter(Assignment.coach_user_id == coach.id)
    if student_id is not None:
        query = query.filter(Assignment.student_user_id == student_id)
    return (
        query.order_by(Assignment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def list_assignments_for_student(
    db: Session, student: User, *, page: int = 1, page_size: int = 50
) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(Assignment.student_user_id == student.id)
        .order_by(Assignment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def list_assignments_for_parent(
    db: Session, *, parent, student_id: int, page: int = 1, page_size: int = 50
) -> list[Assignment] | None:
    """Assignments visible to a parent: the child's rows, gated by an
    ACTIVE parent relationship. None when unauthorized (callers map to
    404). Parents never create, modify, or cancel assignments."""
    student = assert_authorized_student(db, kind=KIND_PARENT, mentor=parent, student_id=student_id)
    if student is None:
        return None
    return (
        db.query(Assignment)
        .filter(Assignment.student_user_id == student.id)
        .order_by(Assignment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def update_assignment(
    db: Session, *, actor: User, assignment_id: int, status: str
) -> tuple[Assignment, bool] | None:
    """Transition an assignment. Terminal states never reopen.

    * coach: assigned -> completed | cancelled
    * student: assigned -> completed (own assignments only)
    """
    clean = str(status or "").strip().lower()
    if clean not in ASSIGNMENT_STATUSES:
        raise ValueError("invalid_status")
    row = get_assignment(db, actor, assignment_id)
    if row is None:
        return None
    if row.status == clean:
        return row, False
    if row.status != "assigned":
        raise ValueError("invalid_transition")
    is_coach = actor.id == row.coach_user_id
    is_student = actor.id == row.student_user_id
    if clean == "completed" and (is_coach or is_student):
        row.status = ASSIGNMENT_COMPLETED
        row.completed_at = _utcnow()
    elif clean == "cancelled" and is_coach:
        row.status = ASSIGNMENT_CANCELLED
    else:
        raise ValueError("update_forbidden")
    db.commit()
    db.refresh(row)
    record_audit(
        db,
        actor_id=actor.id,
        action="assignments.update",
        target_type="assignment",
        target_id=row.id,
        metadata={"status": clean},
    )
    return row, True


__all__ = [
    "KIND_COACH",
    "KIND_PARENT",
    "KINDS",
    "STATUS_ACTIVE",
    "STATUS_PENDING",
    "STATUS_REVOKED",
    "accept_relationship",
    "active_link",
    "assert_authorized_student",
    "create_assignment",
    "create_relationship",
    "display_name_for",
    "find_user_by_username",
    "get_assignment",
    "get_relationship",
    "has_role",
    "list_assignments_for_coach",
    "list_assignments_for_parent",
    "list_assignments_for_student",
    "list_related_students",
    "list_relationships",
    "revoke_relationship",
    "update_assignment",
]
