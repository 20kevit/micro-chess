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
  }) =>
    request<PathStepResponse>("/api/v1/pathfinding/step", {
      method: "POST",
      body: JSON.stringify(body),
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
  validateReverseOpeningStep: (body: {
    puzzle_id: number;
    fen: string;
    moves: string[];
    from: string;
    to: string;
    promotion?: string | null;
  }) =>
    request<ReconstructionStepResponse>("/api/v1/reverse-opening/step", {
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
  // Get Out of Check: White in check, every escaping move as arrows.
  // Same contract as above (public puzzle data only, grading
  // always server-side). Prefetch buffers never carry answers.
  nextGetOutOfCheckPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/get-out-of-check/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startGetOutOfCheckSpeedSession: () =>
    request<SpeedSession>("/api/v1/get-out-of-check/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareGetOutOfCheckSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/get-out-of-check/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startGetOutOfCheckSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/get-out-of-check/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextGetOutOfCheckSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/get-out-of-check/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitGetOutOfCheckSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/get-out-of-check/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGetOutOfCheckSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/get-out-of-check/sessions/${sessionId}`),
  getGetOutOfCheckSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/get-out-of-check/sessions/${sessionId}/report`),
  finishGetOutOfCheckSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/get-out-of-check/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Pathfinding (Exercise 6): one white piece to the star + speed sessions.
  // Same contract as above (public puzzle data only — optimal move counts
  // never leave the server; grading always server-side).
  nextPathfindingPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/pathfinding/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startPathfindingSpeedSession: () =>
    request<SpeedSession>("/api/v1/pathfinding/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  preparePathfindingSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/pathfinding/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startPathfindingSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/pathfinding/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextPathfindingSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/pathfinding/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitPathfindingSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/pathfinding/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPathfindingSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/pathfinding/sessions/${sessionId}`),
  getPathfindingSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/pathfinding/sessions/${sessionId}/report`),
  finishPathfindingSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/pathfinding/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Pathfinding with Obstacles (Exercise 7): one white piece to the star
  // around/through black enemies + speed sessions. Same contract as above
  // (public puzzle data only — optimal move counts never leave the
  // server; grading always server-side). Prefetch buffers never carry
  // answers.
  validateObstacleStep: (body: {
    puzzle_id: number;
    fen: string;
    selected_at: string;
    from: string;
    to: string;
  }) =>
    request<PathStepResponse>("/api/v1/pathfinding-obstacles/step", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  nextObstaclePracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/pathfinding-obstacles/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startObstacleSpeedSession: () =>
    request<SpeedSession>("/api/v1/pathfinding-obstacles/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareObstacleSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startObstacleSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextObstacleSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitObstacleSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getObstacleSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}`),
  getObstacleSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/report`),
  finishObstacleSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/pathfinding-obstacles/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Balance Scale (Exercise 10): match the black left pan with the
  // fewest white pieces + speed sessions. Same contract as above
  // (public puzzle data only — target/optimal counts never leave the
  // server; grading always server-side). Prefetch buffers never carry
  // answers.
  nextBalancePracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/balance-scale/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startBalanceSpeedSession: () =>
    request<SpeedSession>("/api/v1/balance-scale/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareBalanceSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/balance-scale/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startBalanceSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/balance-scale/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextBalanceSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/balance-scale/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitBalanceSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/balance-scale/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getBalanceSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/balance-scale/sessions/${sessionId}`),
  getBalanceSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/balance-scale/sessions/${sessionId}/report`),
  finishBalanceSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/balance-scale/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Heavier Side: real board positions, three material choices + speed sessions.
  // Same contract as above (public puzzle data only — the FEN is visible for
  // rendering, the material verdict never leaves the server; grading always
  // server-side). Prefetch buffers never carry answers.
  nextHeavierPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/heavier-side/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startHeavierSpeedSession: () =>
    request<SpeedSession>("/api/v1/heavier-side/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareHeavierSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/heavier-side/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startHeavierSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/heavier-side/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextHeavierSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/heavier-side/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitHeavierSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/heavier-side/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getHeavierSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/heavier-side/sessions/${sessionId}`),
  getHeavierSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/heavier-side/sessions/${sessionId}/report`),
  finishHeavierSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/heavier-side/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Blindfold Square Vision: one uniform-random square per puzzle + speed
  // sessions. Same contract as above (the square in position_json is the
  // public question; its color never leaves the server; grading always
  // server-side). Prefetch buffers never carry answers.
  nextSquareVisionPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/blindfold-square-vision/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startSquareVisionSpeedSession: () =>
    request<SpeedSession>("/api/v1/blindfold-square-vision/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareSquareVisionSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startSquareVisionSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextSquareVisionSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitSquareVisionSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getSquareVisionSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/blindfold-square-vision/sessions/${sessionId}`),
  getSquareVisionSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/report`),
  finishSquareVisionSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/blindfold-square-vision/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Chinese Board: memorize a real position, rebuild it from memory +
  // speed sessions. Same contract as above (the FEN in position_json is
  // the board shown during memorization; the piece set verdict and the
  // study budget stay server-side; grading always server-side).
  // Prefetch buffers never carry answers.
  nextChinesePracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/chinese-board/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startChineseSpeedSession: () =>
    request<SpeedSession>("/api/v1/chinese-board/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareChineseSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/chinese-board/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startChineseSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/chinese-board/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextChineseSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/chinese-board/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitChineseSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/chinese-board/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getChineseSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/chinese-board/sessions/${sessionId}`),
  getChineseSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/chinese-board/sessions/${sessionId}/report`),
  finishChineseSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/chinese-board/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Blindfold Calculation: real positions as Persian text, best-move SAN
  // answers + speed sessions. Same contract as above (the description in
  // position_json is the public question; the FEN and the solution move
  // never leave the server; grading always server-side). Prefetch buffers
  // never carry answers. No board is ever rendered for this exercise.
  nextBlindfoldCalcPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/blindfold-calculation/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startBlindfoldCalcSpeedSession: () =>
    request<SpeedSession>("/api/v1/blindfold-calculation/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareBlindfoldCalcSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/blindfold-calculation/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startBlindfoldCalcSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/blindfold-calculation/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextBlindfoldCalcSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/blindfold-calculation/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitBlindfoldCalcSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/blindfold-calculation/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getBlindfoldCalcSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/blindfold-calculation/sessions/${sessionId}`),
  getBlindfoldCalcSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/blindfold-calculation/sessions/${sessionId}/report`),
  finishBlindfoldCalcSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/blindfold-calculation/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
  // Trapped Pieces: real positions, select every trapped piece + speed
  // sessions. Same contract as above (public puzzle data only — the FEN is
  // visible for rendering, the trapped set never leaves the server;
  // grading always server-side). Practice positions may hold 1-3 trapped
  // pieces (multi-select + confirm); Speed positions hold exactly one, so
  // one tap submits immediately. Prefetch buffers never carry answers.
  nextTrappedPracticePuzzle: (body?: { exclude_ids?: number[] }) =>
    request<Puzzle>("/api/v1/trapped-pieces/next", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  startTrappedSpeedSession: () =>
    request<SpeedSession>("/api/v1/trapped-pieces/sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  prepareTrappedSpeedPuzzles: (sessionId: string, body: { count: number }) =>
    request<Puzzle[]>(`/api/v1/trapped-pieces/sessions/${sessionId}/puzzles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startTrappedSpeedClock: (sessionId: string) =>
    request<SpeedSession>(`/api/v1/trapped-pieces/sessions/${sessionId}/start`, {
      method: "POST",
    }),
  nextTrappedSpeedPuzzle: (sessionId: string) =>
    request<Puzzle>(`/api/v1/trapped-pieces/sessions/${sessionId}/next`, {
      method: "POST",
    }),
  submitTrappedSpeedAnswer: (
    sessionId: string,
    body: {
      puzzle_id: number;
      answer: Record<string, unknown>;
      hints_used?: string[];
      started_at?: string | null;
    },
  ) =>
    request<SpeedSubmitResponse>(`/api/v1/trapped-pieces/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTrappedSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/trapped-pieces/sessions/${sessionId}`),
  getTrappedSpeedReport: (sessionId: string) =>
    request<SpeedReport>(`/api/v1/trapped-pieces/sessions/${sessionId}/report`),
  finishTrappedSpeedSession: (sessionId: string) =>
    request<SpeedSummary>(`/api/v1/trapped-pieces/sessions/${sessionId}/finish`, {
      method: "POST",
    }),
};
