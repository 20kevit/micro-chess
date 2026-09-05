// Thin HTTP client. Backend is authoritative; this only transports data.
import type {
  AttemptMode,
  AttemptResponse,
  Exercise,
  PathStepResponse,
  Puzzle,
  ReconstructionStepResponse,
  SpeedSession,
  SpeedSubmitResponse,
  SpeedSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`api_error:${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  listExercises: () => request<Exercise[]>("/api/v1/exercises"),
  listPuzzles: (exercise?: string) =>
    request<Puzzle[]>(`/api/v1/puzzles${exercise ? `?exercise=${exercise}` : ""}`),
  getPuzzle: (id: number) => request<Puzzle>(`/api/v1/puzzles/${id}`),
  validatePathStep: (body: {
    puzzle_id: number;
    fen: string;
    selected_at: string;
    from: string;
    to: string;
    promotion?: string;
  }) =>
    request<PathStepResponse>("/api/v1/pathfinding/step", {
      method: "POST",
      body: JSON.stringify({ promotion: "q", ...body }),
    }),
  submitAttempt: (body: {
    puzzle_id: number;
    answer: Record<string, unknown>;
    mode: AttemptMode;
    hints_used?: string[];
    started_at?: string | null;
    client_result?: string | null;
  }) =>
    request<AttemptResponse>("/api/v1/attempts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  validateReconstructionStep: (body: {
    puzzle_id: number;
    fen: string;
    moves: string[];
    from: string;
    to: string;
    promotion?: string | null;
  }) =>
    request<ReconstructionStepResponse>("/api/v1/reconstruction/step", {
      method: "POST",
      body: JSON.stringify({ promotion: "q", ...body }),
    }),
  // Piece Recognition: server-generated random puzzles + speed sessions.
  // Answers stay server-side; these endpoints never return answer_json.
  nextPracticePuzzle: () =>
    request<Puzzle>("/api/v1/piece-recognition/next", { method: "POST" }),
  startSpeedSession: () =>
    request<SpeedSession>("/api/v1/piece-recognition/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  nextSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/piece-recognition/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/piece-recognition/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/piece-recognition/sessions/${sessionId}`),
  finishSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/piece-recognition/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
};
