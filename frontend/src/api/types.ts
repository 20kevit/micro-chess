// Shared API types. Mirror backend schemas; no validation logic here.
export interface Exercise {
  slug: string;
  title_fa: string;
  title_en: string;
  description: string;
  is_active: boolean;
}

export interface Hint {
  id: string;
  text_fa: string;
  rating_cost?: number;
}

export interface Puzzle {
  id: number;
  exercise_slug: string;
  fen: string | null;
  position_json: Record<string, unknown>;
  hint_json: { hints?: Hint[] };
  prompt_fa: string;
  explanation: string;
  initial_rating: number;
  is_published: boolean;
  is_archived: boolean;
}

export type AttemptMode = "rated" | "practice";
export type AttemptResult =
  | "correct"
  | "partial"
  | "wrong"
  | "timeout"
  | "skipped"
  | "abandoned";

export interface PathStepResponse {
  ok: boolean;
  fen: string;
  selected_at: string;
  reached: boolean;
  captured: string | null;
  message_key: string;
}

export interface ReconstructionStepResponse {
  ok: boolean;
  fen: string;
  moves: string[];
  san: string;
  captured: string | null;
  on_track: boolean;
  message_key: string;
}

export interface AttemptResponse {
  id: number;
  puzzle_id: number;
  exercise_slug: string;
  mode: AttemptMode;
  result: AttemptResult;
  score: number;
  feedback_key: string;
  // Server-authoritative rating snapshot (Phase 4). All three travel
  // together for rated attempts; all three are null for practice.
  rating_before: number | null;
  rating_delta: number | null;
  rating_after: number | null;
  // Server-authoritative XP awarded for this attempt (Phase 5).
  // Null for non-qualifying attempts (guests, terminal states).
  xp_awarded?: number | null;
  detail: {
    correct: string[];
    missed: string[];
    wrong: string[];
    missing?: string[];
    extra?: string[];
    correct_squares?: string[];
    missed_squares?: string[];
    wrong_squares?: string[];
    piece_count?: number;
    memorization_ms?: number;
    submitted_value?: number;
    target_value?: number;
    left_value?: number;
    right_value?: number;
    moves?: number;
    path?: string[];
    correct_move?: string;
    theme?: string;
    correct_sequence?: string[];
    submitted_sequence?: string[];
    matched_plies?: number;
    expected_plies?: number;
    expected?: string;
    corners?: string[];
  };
  hints_used: string[];
  started_at: string | null;
  duration_ms: number | null;
}

export type SpeedStatus = "preparing" | "active" | "finished" | "expired";

export interface SpeedSession {
  session_id: string;
  exercise_slug: string;
  status: SpeedStatus;
  duration_s: number;
  started_at: string;
  expires_at: string | null;
  remaining_ms: number;
  buffered: number;
}

export interface SpeedSummary extends SpeedSession {
  attempted: number;
  correct: number;
  partial: number;
  wrong: number;
  score: number;
}

export interface SpeedSubmitResponse {
  attempt: AttemptResponse;
  feedback_key: string;
  detail: AttemptResponse["detail"];
  session: SpeedSummary;
}

export interface ReportEntry {
  attempt_id: number;
  puzzle_id: number;
  prompt_fa: string;
  fen: string | null;
  result: AttemptResult;
  score: number;
  correct: string[];
  missed: string[];
  wrong: string[];
  created_at: string;
}

export interface SpeedReport {
  session: SpeedSummary;
  entries: ReportEntry[];
}

// Player platform (mirrors backend modules/player/schemas.py).
// The server owns identity, ownership, and aggregation; these are read models.
export interface PlayerProfile {
  display_name: string;
  bio: string;
  avatar_reference: string;
  updated_at: string | null;
}

export type ChessProvider = "fide" | "lichess" | "chess_com";

export interface ChessIdentity {
  id: number;
  provider: string;
  username: string;
  rating: number | null;
  rating_type: string | null;
  is_verified: boolean;
}

export interface HistoryAttempt {
  id: number;
  puzzle_id: number;
  exercise_slug: string;
  mode: AttemptMode;
  result: AttemptResult;
  score: number;
  duration_ms: number | null;
  hints_used: string[];
  // Rating snapshot for rated attempts (all null for practice/unrated).
  rating_before: number | null;
  rating_delta: number | null;
  rating_after: number | null;
  // XP awarded for this attempt (null for non-qualifying attempts).
  xp_awarded?: number | null;
  created_at: string;
}

export interface ExerciseProgress {
  exercise: string;
  attempts: number;
  correct: number;
  accuracy: number;
  last_practiced_at: string | null;
}

export interface ProgressSummary {
  attempts: number;
  correct: number;
  accuracy: number;
  exercises: ExerciseProgress[];
}

export interface Dashboard {
  profile: PlayerProfile;
  progress: ProgressSummary;
  recent_attempts: HistoryAttempt[];
}

// Per-exercise MicroChess rating (mirrors backend player/schemas RatingOut).
// Display-only: the server owns every value; nothing here is trusted for logic.
export interface PlayerRating {
  exercise: string;
  rating: number;
  rating_deviation: number;
  provisional: boolean;
  attempts_count: number;
  updated_at: string | null;
}

export interface RatingsResponse {
  items: PlayerRating[];
}

export interface RatingHistoryItem {
  attempt_id: number;
  before: number;
  delta: number;
  after: number;
  rating_deviation_before: number;
  rating_deviation_after: number;
  reason: string;
  occurred_at: string;
}

export interface RatingHistoryResponse {
  items: RatingHistoryItem[];
}

// Gamification (mirrors backend player/schemas gamification outputs).
// Display-only: the server owns every value; nothing here is trusted for logic.
export interface GamificationSummary {
  xp: {
    total: number;
    level: number;
    xp_in_level: number;
    xp_for_next: number;
  };
  streak: {
    current: number;
    longest: number;
  };
  achievements_unlocked: number;
  total_achievements: number;
}

export interface XpHistoryItem {
  attempt_id: number;
  amount: number;
  reason: string;
  balance_after: number;
  occurred_at: string;
}

export interface XpHistoryResponse {
  items: XpHistoryItem[];
}

export interface AchievementItem {
  code: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface AchievementsResponse {
  items: AchievementItem[];
}

// Administration (mirrors backend modules/admin/schemas.py). The server
// owns authorization; these are display/transport shapes only. Admin
// responses never carry passwords, hashes, tokens, or other secrets.
export interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AdminUserDetail extends AdminUser {
  profile: {
    display_name: string;
    bio: string;
    avatar_reference: string;
  };
  attempts_count: number;
}

export interface AdminExercise {
  slug: string;
  title_fa: string;
  title_en: string;
  description: string;
  is_active: boolean;
  sort_order: number;
}

export interface AdminExerciseDetail extends AdminExercise {
  puzzle_count: number;
  attempts_count: number;
}

export interface AdminPuzzle {
  id: number;
  exercise_slug: string;
  status: string;
  fen: string | null;
  position_json: Record<string, unknown>;
  answer_json: Record<string, unknown>;
  hint_json: Record<string, unknown>;
  prompt_fa: string;
  explanation: string;
  initial_rating: number;
  is_published: boolean;
  is_archived: boolean;
  published_at: string | null;
  created_at: string;
  // Phase 07 lifecycle + provenance metadata (display only; the
  // server owns every transition).
  source: string;
  source_reference: string | null;
  generator_run_id: number | null;
  difficulty: number | null;
  target_rating: number | null;
  retired_at: string | null;
}

export interface PuzzleHistory {
  puzzle_id: number;
  status: string;
  transitions: Array<{
    id: number;
    from_status: string;
    to_status: string;
    changed_by_user_id: number | null;
    reason: string;
    created_at: string;
  }>;
  validations: Array<{
    id: number;
    validator_version: string;
    status: string;
    result: { errors?: Array<{ code: string; detail?: string }> };
    validated_by_user_id: number | null;
    created_at: string;
  }>;
  reviews: Array<{
    id: number;
    reviewer_user_id: number | null;
    decision: string;
    notes: string;
    created_at: string;
  }>;
}

// Content generators (mirrors backend modules/generators). Display
// and transport shapes only; generation always runs server-side.
export interface Generator {
  code: string;
  exercise_slug: string;
  version: string;
  description: string;
  config_schema: Record<string, unknown>;
  status: string;
}

export interface GeneratorRun {
  id: number;
  generator_code: string;
  generator_version: string;
  exercise_slug: string;
  status: string;
  requested_count: number;
  generated_count: number;
  validated_count: number;
  accepted_count: number;
  rejected_count: number;
  seed: number | null;
  target_rating: number | null;
  difficulty: number | null;
  config: Record<string, unknown>;
  result: {
    accepted_puzzle_ids?: number[];
    rejected?: Array<{ index: number; reason: string; detail?: string; errors?: unknown }>;
  };
  error: string;
  requested_by_user_id: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface AdminOverview {
  users_total: number;
  users_active: number;
  users_suspended: number;
  exercises_total: number;
  exercises_active: number;
  puzzles_total: number;
  puzzles_published: number;
  puzzles_archived: number;
  attempts_total: number;
  attempts_last_24h: number;
  recent_registrations: Array<{
    id: number;
    username: string;
    display_name: string;
    created_at: string;
  }>;
  recent_audit: Array<{
    id: number;
    actor_user_id: number | null;
    action: string;
    target_type: string;
    target_id: string;
    result: string;
    created_at: string;
  }>;
}

export interface AdminAuditRecord {
  id: number;
  actor_user_id: number | null;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  result: string;
  created_at: string;
}

// Player analytics (mirrors backend modules/analytics/schemas.py).
// Display-only: every number is server-derived; nothing here is trusted.
export type AnalyticsPeriod = "7d" | "30d" | "90d" | "all" | "custom";

export interface AnalyticsModeBreakdown {
  mode: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface AnalyticsExerciseBreakdown {
  exercise: string;
  attempts: number;
  correct: number;
  accuracy: number;
  avg_response_ms: number | null;
  last_practiced_at: string | null;
}

export interface AnalyticsTotals {
  attempts: number;
  correct: number;
  partial: number;
  wrong: number;
  terminal: number;
  accuracy: number;
  avg_response_ms: number | null;
  total_practice_ms: number;
  active_days: number;
}

export interface AnalyticsDailyBucket {
  bucket_start: string;
  attempts: number;
  correct: number;
  accuracy: number;
  xp: number;
}

export interface AnalyticsRatingTrend {
  exercise: string;
  current: number | null;
  provisional: boolean | null;
  games: number;
  events_in_period: number;
  delta_in_period: number;
}

export interface PlayerAnalytics {
  period: string;
  start: string | null;
  end: string;
  exercise: string | null;
  totals: AnalyticsTotals;
  by_mode: AnalyticsModeBreakdown[];
  by_exercise: AnalyticsExerciseBreakdown[];
  daily: AnalyticsDailyBucket[];
  ratings: AnalyticsRatingTrend[];
  xp: { earned_in_period: number; events_in_period: number; total: number; level: number };
  streak: { current: number; longest: number };
}

export interface PlayerComparison {
  period: string;
  exercise: string | null;
  current: {
    start: string;
    end: string;
    attempts: number;
    accuracy: number;
    avg_response_ms: number | null;
    active_days: number;
    xp_earned: number;
    rating_delta: number;
  };
  previous: {
    start: string;
    end: string;
    attempts: number;
    accuracy: number;
    avg_response_ms: number | null;
    active_days: number;
    xp_earned: number;
    rating_delta: number;
  };
  delta: { attempts: number; accuracy: number; active_days: number; xp_earned: number; rating_delta: number };
}

// Admin analytics (mirrors backend admin analytics schemas). Display and
// transport shapes only; authorization stays server-side.
export interface AdminPlatformAnalytics {
  period: string;
  start: string | null;
  end: string;
  users_total: number;
  new_registrations: number;
  active_users: number;
  totals: AnalyticsTotals;
  by_mode: AnalyticsModeBreakdown[];
  exercise_usage: Array<AnalyticsExerciseBreakdown & { unique_players: number }>;
  daily: AnalyticsDailyBucket[];
  ratings: { events_in_period: number; delta_sum_in_period: number; current_rows: number };
  xp: { earned_in_period: number; events_in_period: number };
  comparison: { attempts: number; accuracy: number; active_users: number; xp_earned: number } | null;
}

export interface AdminExerciseAnalytics {
  exercise: string;
  is_active: boolean | null;
  attempts: number;
  unique_players: number;
  correct: number;
  partial: number;
  wrong: number;
  accuracy: number;
  avg_response_ms: number | null;
  active_days: number;
  puzzles_total: number;
  puzzles_published: number;
  rating_events_in_period: number;
  rating_delta_sum_in_period: number;
  current_ratings: number;
  current_rating_avg: number | null;
}

export interface AdminPuzzleAnalytics {
  puzzle_id: number;
  exercise_slug: string;
  status: string;
  difficulty: number | null;
  initial_rating: number;
  attempts: number;
  correct: number;
  accuracy: number;
  failure_rate: number;
  unique_players: number;
  repeated_failures: number;
  observed_difficulty: string;
  avg_response_ms: number | null;
}

// Relationships (mirrors backend modules/relationships/schemas.py).
// Transport shapes only; authorization stays server-side.
export type RelationshipKind = "coach" | "parent";
export type RelationshipStatus = "pending" | "active" | "revoked";

export interface Relationship {
  id: number;
  kind: RelationshipKind;
  status: RelationshipStatus;
  mentor_user_id: number;
  student_user_id: number;
  other_user_id: number;
  other_username: string;
  other_display_name: string;
  created_by_user_id: number | null;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
}

export interface RelatedStudent {
  id: number;
  username: string;
  display_name: string;
}

export type AssignmentStatus = "assigned" | "completed" | "cancelled";

export interface Assignment {
  id: number;
  coach_user_id: number;
  student_user_id: number;
  relationship_id: number;
  exercise_slug: string;
  note: string;
  due_at: string | null;
  status: AssignmentStatus;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

// Authentication state (mirrors backend users/schemas.py UserOut).
// The server owns roles/capabilities; the client only renders them.
// `active_role` is this session's authoritative role (always a member
// of `roles`); route guards and nav prefer it when present.
export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
  active_role: string;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

// Active-role switch result (mirrors backend auth/schemas.py).
export interface ActiveRoleOut {
  active_role: string;
  roles: string[];
}

// Adaptive training (Phase 10). Display-only: every signal, reason, and
// candidate comes from the server; the client never computes policy.
export interface AdaptiveExerciseSignals {
  exercise: string;
  attempts: number;
  accuracy: number;
  recent_accuracy: number | null;
  recent_failures: number;
  repeated_mistakes: number;
  avg_response_ms: number | null;
  days_since_last: number | null;
  rating: number | null;
  provisional: boolean | null;
  games: number;
  rating_trend: number;
  reason: string;
}

export interface AdaptiveOverview {
  exercises: AdaptiveExerciseSignals[];
  recommended_exercise: string | null;
  reason: string | null;
}

export interface AdaptiveNext {
  puzzle: Puzzle;
  reason: string;
  ability_rating: number;
  target_rating: number;
  observed_difficulty: string;
  recommendation_id: number;
  fallback: boolean;
}

export interface AdaptiveRecommendation {
  id: number;
  exercise_slug: string;
  puzzle_id: number;
  reason: string;
  ability_rating: number;
  target_rating: number;
  seed: number | null;
  status: string;
  result: string | null;
  created_at: string;
}

// Support & notifications (Phase 11). Display-only transport: the
// server owns tickets, messages, notifications, and preferences.
export type SupportTicketStatus = "open" | "answered" | "closed";

export interface SupportMessage {
  id: number;
  author: "user" | "staff";
  body: string;
  created_at: string;
}

export interface SupportTicket {
  id: number;
  subject: string;
  category: string;
  status: SupportTicketStatus;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  messages?: SupportMessage[];
  user_id?: number;
  assigned_admin_id?: number | null;
}

export interface NotificationItem {
  id: number;
  type: string;
  category: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPreference {
  category: string;
  channel: string;
  enabled: boolean;
  mandatory: boolean;
}
