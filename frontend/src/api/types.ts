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
  rating_delta: number | null;
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

// Authentication state (mirrors backend users/schemas.py UserOut).
// The server owns roles/capabilities; the client only renders them.
export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}
