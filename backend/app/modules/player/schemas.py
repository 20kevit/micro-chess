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


# --- dashboard ----------------------------------------------------------------------


class DashboardOut(BaseModel):
    profile: ProfileOut
    progress: ProgressOut
    recent_attempts: list[HistoryAttemptOut]
