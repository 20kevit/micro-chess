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

export type SpeedStatus = "active" | "finished" | "expired";

export interface SpeedSession {
  session_id: string;
  exercise_slug: string;
  status: SpeedStatus;
  duration_s: number;
  started_at: string;
  expires_at: string;
  remaining_ms: number;
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
