"""Player platform schemas (API boundary). No secrets, no server-managed fields."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- profile ------------------------------------------------------------------


class ProfileOut(BaseModel):
    display_name: str
    bio: str = ""
    avatar_reference: str = ""
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    # Only editable fields; roles/status/credentials are never writable here.
    # Extra keys are ignored (never mass-assigned onto the account).
    display_name: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    avatar_reference: str | None = Field(default=None, max_length=255)


# --- external chess identities --------------------------------------------------


class IdentityOut(BaseModel):
    id: int
    provider: str
    username: str
    rating: int | None = None
    rating_type: str | None = None
    is_verified: bool = False

    model_config = {"from_attributes": True}


def identity_to_out(identity) -> IdentityOut:
    return IdentityOut(
        id=identity.id,
        provider=identity.provider,
        username=identity.external_username,
        rating=identity.rating,
        rating_type=identity.rating_type,
        is_verified=identity.is_verified,
    )


class IdentityIn(BaseModel):
    provider: str
    username: str = Field(min_length=1, max_length=100)
    rating: int | None = None
    rating_type: str | None = Field(default=None, max_length=30)


class IdentityUpdate(BaseModel):
    # Explicit null clears the optional rating fields; omitted keys are kept.
    # `is_verified` is intentionally absent: verification is server-controlled.
    username: str | None = Field(default=None, max_length=100)
    rating: int | None = None
    rating_type: str | None = Field(default=None, max_length=30)

    def provided(self) -> set[str]:
        return self.model_fields_set


# --- training history ------------------------------------------------------------


class HistoryAttemptOut(BaseModel):
    id: int
    puzzle_id: int
    exercise_slug: str
    mode: str
    result: str
    score: float
    duration_ms: int | None = None
    hints_used: list[str] = []
    # Rating snapshot for rated attempts (all NULL for practice/unrated).
    rating_before: float | None = None
    rating_delta: float | None = None
    rating_after: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- progress ---------------------------------------------------------------------


class ExerciseProgressOut(BaseModel):
    exercise: str
    attempts: int
    correct: int
    accuracy: float
    last_practiced_at: datetime | None = None


class ProgressOut(BaseModel):
    attempts: int
    correct: int
    accuracy: float
    exercises: list[ExerciseProgressOut]


# --- ratings ------------------------------------------------------------------------


class RatingOut(BaseModel):
    exercise: str
    rating: float
    rating_deviation: float
    provisional: bool
    attempts_count: int
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


def rating_to_out(row) -> RatingOut:
    return RatingOut(
        exercise=row.exercise_slug,
        rating=row.rating,
        rating_deviation=row.rating_deviation,
        provisional=row.is_provisional,
        attempts_count=row.games_count,
        updated_at=row.updated_at,
    )


class RatingsOut(BaseModel):
    items: list[RatingOut]


class RatingHistoryItemOut(BaseModel):
    attempt_id: int
    before: float
    delta: float
    after: float
    rating_deviation_before: float
    rating_deviation_after: float
    reason: str
    occurred_at: datetime


def rating_event_to_out(row) -> RatingHistoryItemOut:
    return RatingHistoryItemOut(
        attempt_id=row.attempt_id,
        before=row.rating_before,
        delta=row.rating_delta,
        after=row.rating_after,
        rating_deviation_before=row.rating_deviation_before,
        rating_deviation_after=row.rating_deviation_after,
        reason=row.reason,
        occurred_at=row.created_at,
    )


class RatingHistoryOut(BaseModel):
    items: list[RatingHistoryItemOut]


# --- dashboard ----------------------------------------------------------------------


class DashboardOut(BaseModel):
    profile: ProfileOut
    progress: ProgressOut
    recent_attempts: list[HistoryAttemptOut]
