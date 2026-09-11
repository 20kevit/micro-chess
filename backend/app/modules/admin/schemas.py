"""Administration schemas (API boundary).

Admin responses carry only the fields needed for the task. Password
hashes, emails, session tokens, and other auth secrets never appear.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    roles: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminProfileOut(BaseModel):
    display_name: str = ""
    bio: str = ""
    avatar_reference: str = ""


class AdminUserDetailOut(AdminUserOut):
    profile: AdminProfileOut = AdminProfileOut()
    attempts_count: int = 0


class RoleIn(BaseModel):
    role: str = Field(min_length=1, max_length=20)


class RolesOut(BaseModel):
    roles: list[str]


class ExerciseAdminOut(BaseModel):
    slug: str
    title_fa: str
    title_en: str = ""
    description: str = ""
    is_active: bool = True
    sort_order: int = 0

    model_config = {"from_attributes": True}


class ExerciseAdminDetailOut(ExerciseAdminOut):
    puzzle_count: int = 0
    attempts_count: int = 0


class ExerciseUpdateIn(BaseModel):
    title_fa: str | None = Field(default=None, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PuzzleAdminOut(BaseModel):
    id: int
    exercise_slug: str
    status: str
    fen: str | None = None
    position_json: dict = {}
    # Full admin view: the definitive answer is visible here for review.
    # Player-facing endpoints never use this schema.
    answer_json: dict = {}
    hint_json: dict = {}
    prompt_fa: str = ""
    explanation: str = ""
    initial_rating: float = 1200.0
    is_published: bool
    is_archived: bool
    published_at: datetime | None = None
    created_at: datetime


class PuzzleCreateIn(BaseModel):
    exercise_slug: str = Field(min_length=1, max_length=100)
    fen: str | None = Field(default=None, max_length=255)
    position_json: dict = {}
    answer_json: dict = {}
    hint_json: dict = {}
    prompt_fa: str = Field(default="", max_length=500)
    explanation: str = Field(default="", max_length=2000)
    initial_rating: float = 1200.0


class PuzzleUpdateIn(BaseModel):
    exercise_slug: str | None = Field(default=None, max_length=100)
    fen: str | None = Field(default=None, max_length=255)
    position_json: dict | None = None
    answer_json: dict | None = None
    hint_json: dict | None = None
    prompt_fa: str | None = Field(default=None, max_length=500)
    explanation: str | None = Field(default=None, max_length=2000)
    initial_rating: float | None = None


class RecentRegistrationOut(BaseModel):
    id: int
    username: str
    display_name: str
    created_at: datetime


class RecentAuditOut(BaseModel):
    id: int
    actor_user_id: int | None = None
    action: str
    target_type: str
    target_id: str
    result: str
    created_at: datetime


class OverviewOut(BaseModel):
    users_total: int
    users_active: int
    users_suspended: int
    exercises_total: int
    exercises_active: int
    puzzles_total: int
    puzzles_published: int
    puzzles_archived: int
    attempts_total: int
    attempts_last_24h: int
    recent_registrations: list[RecentRegistrationOut]
    recent_audit: list[RecentAuditOut]


class AuditOut(BaseModel):
    id: int
    actor_user_id: int | None = None
    action: str
    target_type: str
    target_id: str
    metadata: dict = {}
    result: str
    created_at: datetime
