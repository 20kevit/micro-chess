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
    current_plan_code: str | None = None
    current_plan_status: str | None = None
    verification_channel: str | None = None
    phone_verified: bool = False
    last_active_at: datetime | None = None
    attempts_count: int = 0
    coupon_redemption_count: int = 0

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


class ExerciseAdminListOut(ExerciseAdminOut):
    puzzle_count: int = 0
    published_count: int = 0
    needs_review_count: int = 0
    success_rate: float | None = None
    low_supply: bool = False


class ExerciseAdminDetailOut(ExerciseAdminOut):
    puzzle_count: int = 0
    attempts_count: int = 0
    published_count: int = 0
    needs_review_count: int = 0
    success_rate: float | None = None
    low_supply: bool = False


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
    # Phase 07 lifecycle + provenance metadata.
    source: str = "manual"
    source_reference: str | None = None
    generator_run_id: int | None = None
    difficulty: int | None = None
    target_rating: float | None = None
    retired_at: datetime | None = None
    usage_attempts: int = 0


class PuzzleCreateIn(BaseModel):
    exercise_slug: str = Field(min_length=1, max_length=100)
    fen: str | None = Field(default=None, max_length=255)
    position_json: dict = {}
    answer_json: dict = {}
    hint_json: dict = {}
    prompt_fa: str = Field(default="", max_length=500)
    explanation: str = Field(default="", max_length=2000)
    initial_rating: float = 1200.0
    source: str = Field(default="manual", max_length=20)
    source_reference: str | None = Field(default=None, max_length=255)
    difficulty: int | None = Field(default=None)
    target_rating: float | None = Field(default=None)


class PuzzleUpdateIn(BaseModel):
    exercise_slug: str | None = Field(default=None, max_length=100)
    fen: str | None = Field(default=None, max_length=255)
    position_json: dict | None = None
    answer_json: dict | None = None
    hint_json: dict | None = None
    prompt_fa: str | None = Field(default=None, max_length=500)
    explanation: str | None = Field(default=None, max_length=2000)
    initial_rating: float | None = None
    difficulty: int | None = None
    target_rating: float | None = None
    source_reference: str | None = Field(default=None, max_length=255)


class PuzzleReviewIn(BaseModel):
    decision: str = Field(min_length=1, max_length=20)
    notes: str = Field(default="", max_length=2000)


class PuzzleLifecycleIn(BaseModel):
    # Reason/actor/timestamp for quarantine and rejection decisions.
    # Actor and timestamp are server-derived (authenticated user, UTC
    # now) and persisted on the status-history row + audit log.
    reason: str = Field(default="", max_length=500)


class PuzzleHistoryOut(BaseModel):
    puzzle_id: int
    status: str
    transitions: list[dict] = []
    validations: list[dict] = []
    reviews: list[dict] = []


class GeneratorOut(BaseModel):
    code: str
    exercise_slug: str
    version: str
    description: str = ""
    config_schema: dict = {}
    status: str = "active"


class GeneratorRunCreateIn(BaseModel):
    count: int = Field(ge=1, le=50)
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    target_rating: float | None = Field(default=None)
    difficulty: int | None = Field(default=None)
    config: dict = {}


class GeneratorRunOut(BaseModel):
    id: int
    generator_code: str
    generator_version: str
    exercise_slug: str
    status: str
    requested_count: int
    generated_count: int
    validated_count: int
    accepted_count: int
    rejected_count: int
    seed: int | None = None
    target_rating: float | None = None
    difficulty: int | None = None
    config: dict = {}
    result: dict = {}
    error: str = ""
    requested_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


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


class ReviewQueueItemOut(BaseModel):
    id: int
    exercise_slug: str
    status: str
    source: str = "manual"
    difficulty: int | None = None
    initial_rating: float = 1200.0
    created_at: datetime
    attempts: int = 0
    usage_attempts: int = 0
    failure_rate: float | None = None
    severity: str = "normal"
    reasons: list[str] = []
    fen: str | None = None
    position_json: dict = {}
    answer_json: dict = {}
    prompt_fa: str = ""
    explanation: str = ""
    source_reference: str | None = None
    generator_run_id: int | None = None
    validation_status: str | None = None
    latest_validation_status: str | None = None
    creator: dict | None = None
    creator_user_id: int | None = None
    creator_username: str | None = None
    creator_display_name: str | None = None


class RetentionOut(BaseModel):
    cohorts: list[dict] = []
    offsets: list[int] = [1, 7, 14, 30]


class LearningOverviewOut(BaseModel):
    window_days: int = 30
    exercise_usage: list[dict] = []
    mistake_distribution: list[dict] = []
    direction_distribution: list[dict] = []
    top_skills: list[dict] = []


class RecommendationOverviewOut(BaseModel):
    window_days: int = 30
    total: int = 0
    by_status: list[dict] = []
    by_reason: list[dict] = []
    by_exercise: list[dict] = []


class SalesOverviewOut(BaseModel):
    subscriptions_by_status: list[dict] = []
    payments_by_status: list[dict] = []
    revenue_minor: int = 0
    revenue_currency: str = "IRR"
    redemptions_total: int = 0


class InsightOut(BaseModel):
    key: str
    title: str
    severity: str
    domain: str
    entity: str = ""
    evidence: dict = {}
    suggestion: str = ""


class SystemHealthOut(BaseModel):
    ok: bool = False
    database: dict = {}
    schema_status: dict = {}
    puzzles: dict = {}
    providers: dict = {}
    channels: dict = {}


class UserProfileFullOut(BaseModel):
    overview: dict = {}
    learning: dict = {}
    commercial: dict = {}
    timeline: list[dict] = []
    verification: dict = {}


class DashboardExtendedOut(BaseModel):
    users_total: int = 0
    registrations: dict = {}
    active: dict = {}
    attempts: dict = {}
    sales: dict = {}
    alerts: int = 0
    series: list[dict] = []
    attribution: list[dict] = []
    exercise_success: list[dict] = []


class SupportStatsOut(BaseModel):
    by_status: list[dict] = []
    by_category: list[dict] = []
    open: int = 0
    answered: int = 0
    closed: int = 0


# --- Phase 12 content management ------------------------------------------------


class ExerciseCreateIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    title_fa: str = Field(min_length=1, max_length=200)
    title_en: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)


class AnswerContractOut(BaseModel):
    exercise_slug: str
    answer_type: str
    answer_fields: list[dict] = []
    attempt_field: str = ""
    fen_derived: bool = False
    needs_board: bool = True
    position_fields: list[dict] = []
    notes: str = ""
    validator_registered: bool = False
    generator_available: bool = False
    generator_codes: list[str] = []


class PreviewValidateIn(BaseModel):
    exercise_slug: str = Field(min_length=1, max_length=100)
    fen: str | None = Field(default=None, max_length=255)
    position_json: dict = {}
    answer_json: dict = {}
    difficulty: int | None = Field(default=None)
    target_rating: float | None = Field(default=None)
    initial_rating: float | None = Field(default=None)
    prompt_fa: str = Field(default="", max_length=500)
    explanation: str = Field(default="", max_length=2000)
    exclude_puzzle_id: int | None = Field(default=None)


class PreviewValidateOut(BaseModel):
    ok: bool
    errors: list[dict] = []
    content_hash: str = ""


class BulkPuzzleIn(BaseModel):
    puzzle_ids: list[int] = Field(min_length=1, max_length=50)
    action: str = Field(min_length=1, max_length=20)
    reason: str = Field(default="", max_length=500)


class BulkPuzzleOut(BaseModel):
    action: str
    succeeded: list[int] = []
    failed: list[dict] = []


class PuzzleUsageOut(BaseModel):
    puzzle_id: int
    attempts: int = 0
    by_result: dict = {}
    success_rate: float | None = None
    avg_duration_ms: float | None = None
    recent_attempts: int = 20


class ExerciseQualityOut(BaseModel):
    exercise_slug: str
    supply_by_status: list[dict] = []
    published: int = 0
    review_backlog: int = 0
    quarantined: int = 0
    difficulty_distribution: list[dict] = []
    difficulty_levels_covered: list[int] = []
    validation_failures: int = 0
    high_failure_puzzles: list[dict] = []
    attempts: int = 0
    success_rate: float | None = None
    avg_duration_ms: float | None = None
    supply_state: str = "healthy"
    attention_reasons: list[str] = []


class ExerciseLearningOut(BaseModel):
    exercise_slug: str
    window_days: int = 30
    usage: dict = {}
    mistakes: list[dict] = []
    skills: dict = {}
    recommendations: list[dict] = []


class ContentHealthOut(BaseModel):
    low_supply_threshold: int = 5
    exercises: list[dict] = []
    attention_count: int = 0
