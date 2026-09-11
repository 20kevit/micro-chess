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

// Authentication state (mirrors backend users/schemas.py UserOut).
// The server owns roles/capabilities; the client only renders them.
export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  roles: string[];
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}
