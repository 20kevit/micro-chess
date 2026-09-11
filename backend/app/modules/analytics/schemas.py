"""Analytics API schemas (response boundary). Derived read models only."""

from datetime import datetime

from pydantic import BaseModel


class ModeBreakdown(BaseModel):
    mode: str
    attempts: int
    correct: int
    accuracy: float


class ExerciseBreakdown(BaseModel):
    exercise: str
    attempts: int
    correct: int
    accuracy: float
    avg_response_ms: float | None = None
    last_practiced_at: datetime | None = None


class TotalsOut(BaseModel):
    attempts: int
    correct: int
    partial: int
    wrong: int
    terminal: int
    accuracy: float
    avg_response_ms: float | None = None
    total_practice_ms: int
    active_days: int


class DailyBucketOut(BaseModel):
    bucket_start: str
    attempts: int
    correct: int
    accuracy: float
    xp: int


class RatingTrendOut(BaseModel):
    exercise: str
    current: float | None = None
    provisional: bool | None = None
    games: int
    events_in_period: int
    delta_in_period: float


class XpSummaryOut(BaseModel):
    earned_in_period: int
    events_in_period: int
    total: int
    level: int


class StreakSummaryOut(BaseModel):
    current: int
    longest: int


class PlayerAnalyticsOut(BaseModel):
    period: str
    start: datetime | None = None
    end: datetime
    exercise: str | None = None
    totals: TotalsOut
    by_mode: list[ModeBreakdown]
    by_exercise: list[ExerciseBreakdown]
    daily: list[DailyBucketOut]
    ratings: list[RatingTrendOut]
    xp: XpSummaryOut
    streak: StreakSummaryOut


class ComparisonSideOut(BaseModel):
    start: datetime
    end: datetime
    attempts: int
    accuracy: float
    avg_response_ms: float | None = None
    active_days: int
    xp_earned: int
    rating_delta: float


class ComparisonDeltaOut(BaseModel):
    attempts: int
    accuracy: float
    active_days: int
    xp_earned: int
    rating_delta: float


class PlayerComparisonOut(BaseModel):
    period: str
    exercise: str | None = None
    current: ComparisonSideOut
    previous: ComparisonSideOut
    delta: ComparisonDeltaOut


class PlayerPuzzleAnalyticsOut(BaseModel):
    puzzle_id: int
    exercise_slug: str
    attempts: int
    correct: int
    accuracy: float
    avg_response_ms: float | None = None
    last_attempt_at: datetime | None = None


class PlatformComparisonOut(BaseModel):
    attempts: int
    accuracy: float
    active_users: int
    xp_earned: int


class ExerciseUsageOut(ExerciseBreakdown):
    unique_players: int


class PlatformAnalyticsOut(BaseModel):
    period: str
    start: datetime | None = None
    end: datetime
    users_total: int
    new_registrations: int
    active_users: int
    totals: TotalsOut
    by_mode: list[ModeBreakdown]
    exercise_usage: list[ExerciseUsageOut]
    daily: list[DailyBucketOut]
    ratings: dict
    xp: dict
    comparison: PlatformComparisonOut | None = None


class AdminExerciseAnalyticsOut(BaseModel):
    exercise: str
    is_active: bool | None = None
    attempts: int
    unique_players: int
    correct: int
    partial: int
    wrong: int
    accuracy: float
    avg_response_ms: float | None = None
    active_days: int
    puzzles_total: int
    puzzles_published: int
    rating_events_in_period: int
    rating_delta_sum_in_period: float
    current_ratings: int
    current_rating_avg: float | None = None


class AdminExerciseDetailOut(AdminExerciseAnalyticsOut):
    period: str
    start: datetime | None = None
    end: datetime
    terminal: int
    total_practice_ms: int
    by_mode: list[ModeBreakdown]
    daily: list[DailyBucketOut]


class PuzzleAnalyticsOut(BaseModel):
    puzzle_id: int
    exercise_slug: str
    status: str
    difficulty: int | None = None
    initial_rating: float
    attempts: int
    correct: int
    accuracy: float
    failure_rate: float
    unique_players: int
    repeated_failures: int
    observed_difficulty: str
    avg_response_ms: float | None = None


class PuzzleAnalyticsDetailOut(PuzzleAnalyticsOut):
    period: str
    start: datetime | None = None
    end: datetime
    by_mode: list[ModeBreakdown]
    daily: list[DailyBucketOut]
