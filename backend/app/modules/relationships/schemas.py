"""Relationship API schemas (API boundary). No secrets, no auth material."""

from datetime import datetime

from pydantic import BaseModel, Field


class RelationshipCreateIn(BaseModel):
    # Canonical kind: "coach" or "parent".
    kind: str = Field(min_length=1, max_length=20)
    # Username of the other party (mentor invites student or student
    # invites mentor). Usernames are login handles, not secrets; a
    # created invitation is PENDING and grants no access until the other
    # party accepts.
    other_username: str = Field(min_length=1, max_length=30)


class RelationshipOut(BaseModel):
    id: int
    kind: str
    status: str
    mentor_user_id: int
    student_user_id: int
    # Identity of the other party relative to the caller (convenience
    # for request lists; never auth material).
    other_user_id: int
    other_username: str
    other_display_name: str
    created_by_user_id: int | None = None
    created_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


def relationship_to_out(row, *, viewer_id: int, other_username: str, other_display: str) -> RelationshipOut:
    other_id = row.student_user_id if viewer_id == row.mentor_user_id else row.mentor_user_id
    return RelationshipOut(
        id=row.id,
        kind=row.kind,
        status=row.status,
        mentor_user_id=row.mentor_user_id,
        student_user_id=row.student_user_id,
        other_user_id=other_id,
        other_username=other_username,
        other_display_name=other_display,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
    )


class RelatedStudentOut(BaseModel):
    """Privacy-scoped student identity for an authorized mentor.

    Only the fields a coach/parent needs to recognize the student.
    Never credentials, emails, sessions, tokens, or admin data.
    """

    id: int
    username: str
    display_name: str


class AssignmentCreateIn(BaseModel):
    student_id: int
    exercise_slug: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)
    # Optional training goal (free text; no thresholds or rules attached).
    goal: str | None = Field(default=None, max_length=500)
    # Optional ISO-8601 deadline; validated server-side when present.
    due_at: str | None = None


class AssignmentUpdateIn(BaseModel):
    # Only terminal transitions from "assigned" are accepted:
    # "completed" or "cancelled".
    status: str = Field(min_length=1, max_length=20)


class AssignmentOut(BaseModel):
    id: int
    coach_user_id: int
    student_user_id: int
    relationship_id: int
    exercise_slug: str
    note: str
    # Optional training goal (None when the coach set none).
    goal: str | None = None
    # Origin discriminator: always "coach_direct" (server-set; direct
    # work is never mixed with system recommendations).
    source: str
    due_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
