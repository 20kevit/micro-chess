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
  puzzle_count: number;
  published_count: number;
  needs_review_count: number;
  success_rate: number | null;
  low_supply: boolean;
}

export interface AdminExerciseDetail extends AdminExercise {
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

// Phase 12 content management: answer contracts, quality, learning,
// bulk operations, and content health (mirrors backend admin/content.py).
export interface AnswerContract {
  exercise_slug: string;
  answer_type: string;
  answer_fields: Array<{
    name: string;
    kind: string;
    description: string;
    item_hint?: string;
    options?: string[];
  }>;
  attempt_field: string;
  fen_derived: boolean;
  needs_board: boolean;
  position_fields: Array<{ name: string; kind: string; description: string }>;
  notes: string;
  validator_registered: boolean;
  generator_available: boolean;
  generator_codes: string[];
}

export interface PreviewValidation {
  ok: boolean;
  errors: Array<{ code: string; detail?: string; duplicate_of?: number }>;
  content_hash: string;
}

export interface BulkResult {
  action: string;
  succeeded: number[];
  failed: Array<{ id: number; error: string }>;
}

export interface PuzzleUsage {
  puzzle_id: number;
  attempts: number;
  by_result: Record<string, number>;
  success_rate: number | null;
  avg_duration_ms: number | null;
  recent_attempts: number;
}

export interface ExerciseQuality {
  exercise_slug: string;
  supply_by_status: Array<{ status: string; count: number }>;
  published: number;
  review_backlog: number;
  quarantined: number;
  difficulty_distribution: Array<{ difficulty: number | null; count: number }>;
  difficulty_levels_covered: number[];
  validation_failures: number;
  high_failure_puzzles: Array<{ puzzle_id: number; attempts: number; failure_rate: number }>;
  attempts: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
  supply_state: string;
  attention_reasons: string[];
}

export interface ExerciseLearning {
  exercise_slug: string;
  window_days: number;
  usage: {
    attempts: number;
    correct: number;
    success_rate: number | null;
    active_users: number;
    avg_duration_ms: number | null;
    by_result: Array<{ result: string; count: number }>;
  };
  mistakes: Array<{ mistake: string; count: number }>;
  skills: {
    primary: string | null;
    secondary: Array<{ skill: string; link: string }>;
    evidence: Array<{ skill_key: string; direction: string; count: number }>;
  };
  recommendations: Array<{ status: string; count: number }>;
}

export interface ContentHealthRow {
  slug: string;
  title_fa: string;
  is_active: boolean;
  published: number;
  total: number;
  needs_review: number;
  quarantined: number;
  attempts: number;
  success_rate: number | null;
  generator_available: boolean;
  generator_codes: string[];
  supply_state: string;
  reasons: string[];
}

export interface ContentHealth {
  low_supply_threshold: number;
  exercises: ContentHealthRow[];
  attention_count: number;
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

export interface AdminExerciseAnalyticsDetail extends AdminExerciseAnalytics {
  period: string;
  start: string | null;
  end: string;
  terminal: number;
  total_practice_ms: number;
  by_mode: Array<{ mode: string; attempts: number; correct: number; accuracy: number }>;
  daily: Array<{ bucket_start: string; attempts: number; correct: number; accuracy: number; xp: number }>;
  supply_by_status: Array<{ status: string; count: number }>;
  difficulty_distribution: Array<{ difficulty: number | null; count: number }>;
  mistake_distribution: Array<{ mistake: string; count: number }>;
  recommendation_outcomes: Array<{ status: string; count: number }>;
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

// P8 recommendation (mirrors backend recommendations/schemas.py).
// Read-only derivation: the server owns selection; the client only
// renders the suggested exercise and links into the existing attempt
// flow. `reason` is machine-readable for i18n; the internal `trace`
// never leaves the server.
export interface Recommendation {
  exercise_slug: string;
  puzzle_id: number;
  reason: string;
  assignment_id: number | null;
}

// Billing (mirrors backend modules/billing/schemas.py). Display and
// transport shapes only; prices, discounts, and access are computed
// server-side and never trusted from the client.
export interface PlanPrice {
  version: number;
  amount_minor: number;
  currency: string;
  billing_interval: string;
}

export interface BillingPlan {
  code: string;
  name_fa: string;
  description_fa: string;
  billing_interval: string;
  is_active: boolean;
  sort_order: number;
  prices: PlanPrice[];
}

export interface Subscription {
  id: number;
  plan_code: string;
  status: string;
  source: string;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  price_amount_minor: number | null;
  price_currency: string;
  coupon_code: string | null;
  created_at: string;
}

export interface Entitlements {
  plan_code: string;
  status: string;
  has_paid_access: boolean;
  features: string[];
}

export interface CouponQuote {
  code: string;
  discount_type: string;
  plan_code: string;
  price_amount_minor: number | null;
  currency: string;
  discount_minor: number;
  trial_days: number;
  final_amount_minor: number | null;
}

export interface Redemption {
  id: number;
  coupon_code: string;
  status: string;
  discount_granted_minor: number;
  trial_days_granted: number;
  plan_code: string;
  subscription_id: number | null;
  already: boolean;
}

export interface CampaignReport {
  slug: string;
  source: string;
  medium: string;
  registrations: number;
  redemptions: number;
  trials: number;
  paid: number;
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

// Admin operations (mirrors backend modules/admin/ops.py + schemas).
// All aggregates are server-derived; the client only renders them.
export interface ReviewQueueItem {
  id: number;
  exercise_slug: string;
  status: string;
  source: string;
  difficulty: number | null;
  initial_rating: number;
  created_at: string;
  attempts: number;
  failure_rate: number | null;
  severity: string;
  reasons: string[];
}

export interface UserProfileFull {
  overview: {
    id: number;
    username: string;
    display_name: string;
    roles: string[];
    is_active: boolean;
    created_at: string;
    last_active_at: string | null;
    attempts_total: number;
  };
  learning: {
    attempts_by_exercise: Array<{ exercise_slug: string; attempts: number; correct: number }>;
    skills: Array<{ skill: string; level: string; confidence: string; evidence_count: number }>;
    overall_level: string;
    overall_confidence: string;
    mastery: Array<{ skill: string; status: string; confidence: string; attempts: number }>;
    xp: { total: number; level: number } | null;
    streak: { current: number; longest: number } | null;
  };
  commercial: {
    current_subscription: {
      plan_code: string;
      status: string;
      source: string;
      trial_ends_at: string | null;
      current_period_end: string | null;
      coupon_code: string | null;
    } | null;
    subscriptions: Array<{ id: number; plan_code: string; status: string; source: string; created_at: string }>;
    attribution: {
      first_source: string;
      first_campaign: string;
      first_coupon_code: string;
      first_touched_at: string;
      last_source: string;
    } | null;
    redemptions: Array<{ code: string; status: string; discount_granted_minor: number; trial_days_granted: number; created_at: string }>;
    payments: Array<{ id: number; plan_code: string; final_amount_minor: number; currency: string; status: string; provider: string; created_at: string }>;
  };
  timeline: Array<{ kind: string; at: string; detail: string; durable: boolean }>;
}

export interface DashboardExtended {
  users_total: number;
  registrations: { today: number; week: number; month: number };
  active: { today: number; week: number };
  attempts: { today: number; week: number; prev_week: number };
  sales: {
    subscriptions_by_status: Array<{ status: string; count: number }>;
    payments_by_status: Array<{ status: string; count: number }>;
    revenue_minor: number;
    revenue_currency: string;
    redemptions_total: number;
  };
  alerts: number;
  series: Array<{
    day: string;
    registrations: number;
    attempts: number;
    revenue_minor: number;
    redemptions: number;
    new_subscriptions: number;
  }>;
  attribution: Array<{
    slug: string;
    source: string;
    medium: string;
    registrations: number;
    redemptions: number;
    trials: number;
    paid: number;
  }>;
  exercise_success: Array<{ exercise_slug: string; attempts: number; success_rate: number | null }>;
}

export interface RetentionData {
  cohorts: Array<{ cohort: string; size: number; rates: Record<string, number | null> }>;
  offsets: number[];
}

export interface LearningOverview {
  window_days: number;
  exercise_usage: Array<{
    exercise_slug: string;
    attempts: number;
    correct: number;
    success_rate: number | null;
    users: number;
  }>;
  mistake_distribution: Array<{ mistake: string; count: number }>;
  direction_distribution: Array<{ direction: string; count: number }>;
  top_skills: Array<{ skill_key: string; count: number }>;
}

export interface RecommendationOverview {
  window_days: number;
  total: number;
  by_status: Array<{ status: string; count: number }>;
  by_reason: Array<{ reason: string; count: number }>;
  by_exercise: Array<{ exercise_slug: string; count: number }>;
}

export interface SalesOverview {
  subscriptions_by_status: Array<{ status: string; count: number }>;
  payments_by_status: Array<{ status: string; count: number }>;
  revenue_minor: number;
  revenue_currency: string;
  redemptions_total: number;
}

export interface ProductInsight {
  key: string;
  title: string;
  severity: string;
  domain: string;
  entity: string;
  evidence: Record<string, unknown>;
  suggestion: string;
}

export interface SystemHealth {
  ok: boolean;
  database: { reachable: boolean };
  schema_status: { expected: number | null; stored: number | null; ok: boolean };
  puzzles: { total: number; published: number };
}

export interface SupportStats {
  by_status: Array<{ status: string; count: number }>;
  by_category: Array<{ category: string; count: number }>;
  open: number;
  answered: number;
  closed: number;
}

export interface AdminCoupon {
  id: number;
  code: string;
  campaign_slug: string | null;
  discount_type: string;
  discount_value: number;
  trial_days: number;
  is_active: boolean;
  valid_from: string | null;
  valid_until: string | null;
  max_redemptions: number | null;
  max_per_user: number;
  total_redemptions: number;
  applicable_plan_codes: string[];
}

export interface AdminPrice {
  id: number;
  version: number;
  amount_minor: number;
  currency: string;
  billing_interval: string;
  is_active: boolean;
  effective_from: string | null;
}

export interface AdminPlan {
  code: string;
  name_fa: string;
  description_fa: string;
  billing_interval: string;
  is_active: boolean;
  sort_order: number;
  prices: AdminPrice[];
}

export interface AdminCampaign {
  slug: string;
  name_fa: string;
  source: string;
  medium: string;
  content: string;
  is_active: boolean;
}

// Phone verification (Telegram/Bale contact sharing) and daily quota.
// Transport only; the backend owns sessions, contacts, decisions, and
// entitlement resolution.
export interface VerificationSession {
  channel: string;
  pairing_code: string;
  bot_username: string;
  bot_url: string;
  expires_at: string;
}

export interface VerificationStatus {
  verified: boolean;
  phone_masked: string;
  channel: string | null;
}

export interface Quota {
  used: number;
  limit: number;
  remaining: number;
  plan: string;
  local_date: string;
  can_practice: boolean;
  upgrade_available: boolean;
}

export interface PremiumQuote {
  plan_code: string;
  plan_name_fa: string;
  price_amount_minor: number;
  currency: string;
  discount_minor: number;
  final_amount_minor: number;
  coupon_code: string | null;
  gateway_required: boolean;
}

export interface PremiumActivation {
  subscription_id: number;
  plan_code: string;
  status: string;
  final_amount_minor: number;
  already: boolean;
}

export interface Onboarding {
  experience: string;
  play_frequency: string;
  fide_rating: number | null;
  lichess_username: string;
  chesscom_username: string;
  goal: string;
  intensity: string;
  timezone: string;
  onboarding_completed: boolean;
  placement_completed: boolean;
}

export interface PlacementItem {
  exercise_slug: string;
  puzzle_id: number;
  reason: string;
}

export interface TrainingPlan {
  onboarding_completed: boolean;
  placement_completed: boolean;
  intensity: string;
  goal_text: string;
  focus_exercise: string | null;
  headline: string;
  summary: string;
}

export interface Quest {
  id: number;
  slot: number;
  kind: string;
  title: string;
  description: string;
  exercise_slug: string;
  puzzle_id: number | null;
  target_count: number;
  progress: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  local_date: string;
}

export interface TodayJourney {
  local_date: string;
  timezone: string;
  completed_count: number;
  total: number;
  is_complete: boolean;
  quests: Quest[];
}

export interface PushSubscription {
  endpoint: string;
  created_at: string | null;
}

export interface ChannelLink {
  channel: string;
  linked: boolean;
}

