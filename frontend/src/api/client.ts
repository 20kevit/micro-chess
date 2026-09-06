// Thin HTTP client. Backend is authoritative; this only transports data.
import type {
  AttemptMode,
  AttemptResponse,
  Exercise,
  PathStepResponse,
  Puzzle,
  ReconstructionStepResponse,
  SpeedReport,
  SpeedSession,
  SpeedSubmitResponse,
  SpeedSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// Structured transport error. `message` keeps the legacy `api_error:{status}`
// shape (callers match on it); `status`/`detail` carry the authoritative
// backend reason (e.g. session_not_found vs puzzle_not_in_session) so the
// UI can recover precisely instead of showing one generic error.
export interface ApiError extends Error {
  status: number;
  detail: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // Non-JSON error body (proxy/gateway HTML): status is all we have.
    }
    const err = new Error(`api_error:${res.status}${detail ? `:${detail}` : ""}`) as ApiError;
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json() as Promise<T>;
}

export function apiStatus(e: unknown): number | null {
  return e instanceof Error && typeof (e as ApiError).status === "number"
    ? (e as ApiError).status
    : null;
}

export function apiDetail(e: unknown): string {
  return e instanceof Error && typeof (e as ApiError).detail === "string"
    ? (e as ApiError).detail
    : "";
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
  // Prefetch-friendly: buffers of public puzzle data are cheap; grading
  // always revalidates server-side per submission.
  nextPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/piece-recognition/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startSpeedSession: () =>
    request<SpeedSession>("/api/v1/piece-recognition/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/piece-recognition/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/piece-recognition/sessions/${sessionId}/start`, {
      method: "POST",
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
  getSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/piece-recognition/sessions/${sessionId}/report`),
  finishSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/piece-recognition/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Legal Destinations: server-generated white-only puzzles + speed sessions.
  // Same contract as Piece Recognition (public puzzle data only, grading
  // always server-side). Prefetch buffers never carry answers.
  nextLegalPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/legal-destinations/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startLegalSpeedSession: () =>
    request<SpeedSession>("/api/v1/legal-destinations/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareLegalSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/legal-destinations/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startLegalSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/legal-destinations/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextLegalSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/legal-destinations/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitLegalSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/legal-destinations/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getLegalSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/legal-destinations/sessions/${sessionId}`),
  getLegalSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/legal-destinations/sessions/${sessionId}/report`),
  finishLegalSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/legal-destinations/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Captures: one white hunter vs black pieces + speed sessions.
  // Same contract as above (public puzzle data only, grading
  // always server-side). Prefetch buffers never carry answers.
  nextCapturePracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/captures/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startCaptureSpeedSession: () =>
    request<SpeedSession>("/api/v1/captures/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareCaptureSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/captures/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startCaptureSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/captures/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextCaptureSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/captures/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitCaptureSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/captures/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCaptureSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/captures/sessions/${sessionId}`),
  getCaptureSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/captures/sessions/${sessionId}/report`),
  finishCaptureSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/captures/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Undefended Pieces: random shared positions + speed sessions.
  // Same contract as above (public puzzle data only, grading
  // always server-side). Prefetch buffers never carry answers.
  nextUndefendedPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/undefended-pieces/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startUndefendedSpeedSession: () =>
    request<SpeedSession>("/api/v1/undefended-pieces/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareUndefendedSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/undefended-pieces/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startUndefendedSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/undefended-pieces/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextUndefendedSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/undefended-pieces/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitUndefendedSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/undefended-pieces/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getUndefendedSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/undefended-pieces/sessions/${sessionId}`),
  getUndefendedSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/undefended-pieces/sessions/${sessionId}/report`),
  finishUndefendedSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/undefended-pieces/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Giving Check: random shared positions, all checking moves as arrows.
  // Same contract as above (public puzzle data only, grading
  // always server-side). Prefetch buffers never carry answers.
  nextGiveCheckPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/giving-check/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startGiveCheckSpeedSession: () =>
    request<SpeedSession>("/api/v1/giving-check/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareGiveCheckSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/giving-check/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startGiveCheckSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/giving-check/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextGiveCheckSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/giving-check/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitGiveCheckSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/giving-check/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGiveCheckSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/giving-check/sessions/${sessionId}`),
  getGiveCheckSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/giving-check/sessions/${sessionId}/report`),
  finishGiveCheckSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/giving-check/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
};
