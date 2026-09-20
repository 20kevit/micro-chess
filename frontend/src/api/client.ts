// Thin HTTP client. Backend is authoritative; this only transports data.
import type {
  AchievementsResponse,
  ActiveRoleOut,
  AdaptiveNext,
  AdaptiveOverview,
  AdaptiveRecommendation,
  Recommendation,
  AdminAuditRecord,
  AdminExercise,
  AdminExerciseAnalytics,
  AdminExerciseDetail,
  AdminOverview,
  AdminPlatformAnalytics,
  AdminPuzzle,
  AdminPuzzleAnalytics,
  AdminUser,
  AdminUserDetail,
  Assignment,
  AttemptMode,
  AttemptResponse,
  AuthToken,
  AuthUser,
  BillingPlan,
  CampaignReport,
  ChessIdentity,
  CouponQuote,
  Dashboard,
  Entitlements,
  Exercise,
  ExerciseProgress,
  GamificationSummary,
  Generator,
  GeneratorRun,
  HistoryAttempt,
  NotificationItem,
  NotificationPreference,
  PathStepResponse,
  PlayerAnalytics,
  PlayerComparison,
  PlayerProfile,
  PlayerRating,
  ProgressSummary,
  Puzzle,
  PuzzleHistory,
  RatingHistoryResponse,
  RatingsResponse,
  ReconstructionStepResponse,
  Redemption,
  RelatedStudent,
  Relationship,
  SpeedReport,
  SpeedSession,
  SpeedSubmitResponse,
  SpeedSummary,
  Subscription,
  SupportMessage,
  SupportTicket,
  XpHistoryResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// Authentication token transport. The token lives in localStorage so
// anonymous local progress survives reloads; the server remains the
// source of truth (it validates the token on every request).
const TOKEN_KEY = "microchess.auth.token.v1";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage blocked: session simply won't persist across reloads.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore: nothing persisted.
  }
}

// Structured transport error. `message` keeps the legacy `api_error:{status}`
// shape (callers match on it); `status`/`detail` carry the authoritative
// backend reason (e.g. session_not_found vs puzzle_not_in_session) so the
// UI can recover precisely instead of showing one generic error.
// `code` reads the new `error.code` envelope; `detail` keeps the legacy
// field both shapes still carry.
export interface ApiError extends Error {
  status: number;
  detail: string;
  code: string;
  // Structured `error.details` from the backend envelope (e.g. the
  // assigned `roles` on 409 role_selection_required). Transport only.
  details: Record<string, unknown>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail = "";
    let code = "";
    let details: Record<string, unknown> = {};
    try {
      const data = (await res.json()) as {
        detail?: unknown;
        error?: { code?: unknown; details?: unknown };
      };
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail)) detail = "validation_error";
      if (typeof data?.error?.code === "string") code = data.error.code;
      if (data?.error?.details !== null && typeof data?.error?.details === "object") {
        details = data.error.details as Record<string, unknown>;
      }
    } catch {
      // Non-JSON error body (proxy/gateway HTML): status is all we have.
    }
    const err = new Error(`api_error:${res.status}${detail ? `:${detail}` : ""}`) as ApiError;
    err.status = res.status;
    err.detail = detail;
    err.code = code;
    err.details = details;
    throw err;
  }
  if (res.status === 204) return undefined as T;
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

export function apiCode(e: unknown): string {
  return e instanceof Error && typeof (e as ApiError).code === "string"
    ? (e as ApiError).code
    : "";
}

export function apiDetails(e: unknown): Record<string, unknown> {
  if (e instanceof Error) {
    const details = (e as ApiError).details;
    if (details !== null && typeof details === "object") return details;
  }
  return {};
}

export function apiRoles(e: unknown): string[] {
  const roles = apiDetails(e).roles;
  return Array.isArray(roles) ? roles.filter((r): r is string => typeof r === "string") : [];
}

function analyticsQuery(params?: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== "") query.set(key, value);
  }
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
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
  // Authentication transport. The server owns identity, roles, and
  // sessions; these functions only carry credentials and tokens.
  // Attribution extras are best-effort: invalid coupons never break
  // registration (the server validates separately).
  register: (body: {
    username: string;
    password: string;
    display_name?: string;
    coupon_code?: string;
    campaign_slug?: string;
    source?: string;
    medium?: string;
    content?: string;
    landing_path?: string;
    referrer?: string;
  }) =>
    request<AuthToken>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (body: { username: string; password: string; role?: string }) =>
    request<AuthToken>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  switchActiveRole: (role: string) =>
    request<ActiveRoleOut>("/api/v1/auth/active-role", {
      method: "POST",
      body: JSON.stringify({ role }),
    }),
  logout: () =>
    request<void>("/api/v1/auth/logout", {
      method: "POST",
    }),
  me: () => request<AuthUser>("/api/v1/users/me"),
  // Player platform transport. Ownership always derives from the
  // authenticated session; no user ids travel in these requests.
  getProfile: () => request<PlayerProfile>("/api/v1/me/profile"),
  updateProfile: (body: { display_name?: string; bio?: string; avatar_reference?: string }) =>
    request<PlayerProfile>("/api/v1/me/profile", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listIdentities: () => request<ChessIdentity[]>("/api/v1/me/chess-identities"),
  addIdentity: (body: {
    provider: string;
    username: string;
    rating?: number | null;
    rating_type?: string | null;
  }) =>
    request<ChessIdentity>("/api/v1/me/chess-identities", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateIdentity: (
    id: number,
    body: { username?: string; rating?: number | null; rating_type?: string | null },
  ) =>
    request<ChessIdentity>(`/api/v1/me/chess-identities/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteIdentity: (id: number) =>
    request<void>(`/api/v1/me/chess-identities/${id}`, {
      method: "DELETE",
    }),
  trainingAttempts: (params?: {
    exercise?: string;
    mode?: AttemptMode;
    correct?: boolean;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.exercise) query.set("exercise", params.exercise);
    if (params?.mode) query.set("mode", params.mode);
    if (params?.correct !== undefined) query.set("correct", String(params.correct));
    if (params?.page !== undefined) query.set("page", String(params.page));
    if (params?.page_size !== undefined) query.set("page_size", String(params.page_size));
    const suffix = query.toString();
    return request<HistoryAttempt[]>(`/api/v1/me/training/attempts${suffix ? `?${suffix}` : ""}`);
  },
  trainingAttempt: (id: number) => request<HistoryAttempt>(`/api/v1/me/training/attempts/${id}`),
  progress: () => request<ProgressSummary>("/api/v1/me/progress"),
  exerciseProgress: (slug: string) => request<ExerciseProgress>(`/api/v1/me/progress/${slug}`),
  // Player ratings (Phase 4). Read-only display data; the server owns
  // every value and there is no client-facing rating-write endpoint.
  getRatings: () => request<RatingsResponse>("/api/v1/me/ratings"),
  getExerciseRating: (slug: string) => request<PlayerRating>(`/api/v1/me/ratings/${slug}`),
  getRatingHistory: (slug: string) =>
    request<RatingHistoryResponse>(`/api/v1/me/ratings/${slug}/history`),
  // Player gamification (Phase 5). Read-only display data; the server
  // owns every value and there is no client-facing gamification-write
  // endpoint.
  getGamification: () => request<GamificationSummary>("/api/v1/me/gamification"),
  getXpHistory: () => request<XpHistoryResponse>("/api/v1/me/gamification/xp"),
  getAchievements: () => request<AchievementsResponse>("/api/v1/me/achievements"),
  // Player analytics (Phase 8). Read-only derived metrics; the server
  // owns every value, period semantics, and ownership scope.
  getAnalytics: (params?: { period?: string; date_from?: string; date_to?: string; exercise?: string }) =>
    request<PlayerAnalytics>(`/api/v1/me/analytics${analyticsQuery(params)}`),
  getAnalyticsComparison: (params?: { period?: string; date_from?: string; date_to?: string; exercise?: string }) =>
    request<PlayerComparison>(`/api/v1/me/analytics/comparison${analyticsQuery(params)}`),
  getExerciseAnalytics: (slug: string, params?: { period?: string; date_from?: string; date_to?: string }) =>
    request<PlayerAnalytics>(`/api/v1/me/analytics/exercises/${slug}${analyticsQuery(params)}`),
  dashboard: () => request<Dashboard>("/api/v1/me/dashboard"),
  // Adaptive training (Phase 10). Transport only: signals, reasons,
  // and candidates are server-computed; outcome posts only advance the
  // learner's own recommendation lifecycle.
  adaptiveOverview: () => request<AdaptiveOverview>("/api/v1/me/adaptive/overview"),
  adaptiveNext: (exercise: string) =>
    request<AdaptiveNext>(`/api/v1/me/adaptive/next?exercise=${encodeURIComponent(exercise)}`),
  adaptiveOutcome: (id: number, body: { status: string; result?: string }) =>
    request<AdaptiveRecommendation>(`/api/v1/me/adaptive/outcomes/${id}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  adaptiveHistory: () => request<AdaptiveRecommendation[]>("/api/v1/me/adaptive/history"),
  // P8 recommendation (read-only derivation; no writes, no trace).
  recommendation: () => request<Recommendation | null>("/api/v1/me/recommendations"),
  exerciseDetail: (slug: string) => request<Exercise>(`/api/v1/exercises/${slug}`),
  // Own assignments from an authorized coach (read + mark completed).
  myAssignments: () => request<Assignment[]>("/api/v1/me/assignments"),
  completeAssignment: (id: number) =>
    request<Assignment>(`/api/v1/me/assignments/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "completed" }),
    }),
  // Guest identity transport (server-controlled temporary sessions).
  createGuestSession: () =>
    request<{ guest_token: string; expires_at: string }>("/api/v1/guest/session", {
      method: "POST",
    }),
  getGuestSession: (guestToken: string) =>
    request<{ active: boolean; expires_at: string }>("/api/v1/guest/session", {
      headers: { Authorization: `Bearer ${guestToken}` },
    }),
  migrateGuest: (guestToken: string) =>
    request<{ migrated_attempts: number; already_migrated: boolean }>("/api/v1/guest/migrate", {
      method: "POST",
      body: JSON.stringify({ guest_token: guestToken }),
    }),
};

// Support & notifications transport (Phase 11). UX only — ownership,
// capabilities, preferences, and delivery are enforced server-side.
export const supportApi = {
  create: (body: { subject: string; message: string; category?: string }) =>
    request<SupportTicket>("/api/v1/support/tickets", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  myTickets: (params?: { status?: string; page?: number; page_size?: number }) =>
    request<SupportTicket[]>(`/api/v1/me/support/tickets${adminQuery(params)}`),
  myTicket: (id: number) => request<SupportTicket>(`/api/v1/me/support/tickets/${id}`),
  reply: (id: number, body: string) =>
    request<SupportMessage>(`/api/v1/me/support/tickets/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
};

export const notificationsApi = {
  list: (params?: { unread_only?: boolean; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params?.unread_only) query.set("unread_only", "true");
    if (params?.page !== undefined) query.set("page", String(params.page));
    if (params?.page_size !== undefined) query.set("page_size", String(params.page_size));
    const suffix = query.toString();
    return request<NotificationItem[]>(`/api/v1/me/notifications${suffix ? `?${suffix}` : ""}`);
  },
  unreadCount: () => request<{ unread_count: number }>("/api/v1/me/notifications/unread-count"),
  markRead: (id: number) =>
    request<NotificationItem>(`/api/v1/me/notifications/${id}/read`, { method: "POST" }),
  preferences: () => request<NotificationPreference[]>("/api/v1/me/notification-preferences"),
  updatePreference: (body: { category: string; channel: string; enabled: boolean }) =>
    request<NotificationPreference>("/api/v1/me/notification-preferences", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};

// Relationships transport (Phase 9). UX only — every endpoint
// authorizes server-side via capability + active relationship.
export const relationshipsApi = {
  list: (params?: { kind?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.kind) query.set("kind", params.kind);
    if (params?.status) query.set("status", params.status);
    const suffix = query.toString();
    return request<Relationship[]>(`/api/v1/relationships${suffix ? `?${suffix}` : ""}`);
  },
  create: (body: { kind: string; other_username: string }) =>
    request<Relationship>("/api/v1/relationships", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accept: (id: number) =>
    request<Relationship>(`/api/v1/relationships/${id}/accept`, { method: "POST" }),
  revoke: (id: number) =>
    request<Relationship>(`/api/v1/relationships/${id}/revoke`, { method: "POST" }),
};

function studentReads(base: string) {
  return {
    students: () => request<RelatedStudent[]>(`${base}/students`),
    student: (id: number) => request<RelatedStudent>(`${base}/students/${id}`),
    progress: (id: number) => request<ProgressSummary>(`${base}/students/${id}/progress`),
    attempts: (id: number) => request<HistoryAttempt[]>(`${base}/students/${id}/attempts`),
    ratings: (id: number) => request<RatingsResponse>(`${base}/students/${id}/ratings`),
    gamification: (id: number) => request<GamificationSummary>(`${base}/students/${id}/gamification`),
    achievements: (id: number) => request<AchievementsResponse>(`${base}/students/${id}/achievements`),
    analytics: (id: number, params?: { period?: string }) => {
      const query = new URLSearchParams();
      if (params?.period) query.set("period", params.period);
      const suffix = query.toString();
      return request<PlayerAnalytics>(`${base}/students/${id}/analytics${suffix ? `?${suffix}` : ""}`);
    },
    adaptive: (id: number) => request<AdaptiveOverview>(`${base}/students/${id}/adaptive/overview`),
  };
}

function childrenReads(base: string) {
  return {
    children: () => request<RelatedStudent[]>(`${base}/children`),
    child: (id: number) => request<RelatedStudent>(`${base}/children/${id}`),
    progress: (id: number) => request<ProgressSummary>(`${base}/children/${id}/progress`),
    attempts: (id: number) => request<HistoryAttempt[]>(`${base}/children/${id}/attempts`),
    ratings: (id: number) => request<RatingsResponse>(`${base}/children/${id}/ratings`),
    gamification: (id: number) => request<GamificationSummary>(`${base}/children/${id}/gamification`),
    achievements: (id: number) => request<AchievementsResponse>(`${base}/children/${id}/achievements`),
    analytics: (id: number, params?: { period?: string }) => {
      const query = new URLSearchParams();
      if (params?.period) query.set("period", params.period);
      const suffix = query.toString();
      return request<PlayerAnalytics>(`${base}/children/${id}/analytics${suffix ? `?${suffix}` : ""}`);
    },
    adaptive: (id: number) => request<AdaptiveOverview>(`${base}/children/${id}/adaptive/overview`),
    assignments: (id: number) => request<Assignment[]>(`${base}/children/${id}/assignments`),
  };
}

// Coach reads (active coach-student relationship required server-side)
// plus assignment management (blocked without an active relationship).
export const coachApi = {
  ...studentReads("/api/v1/coach"),
  assignments: (studentId?: number) =>
    request<Assignment[]>(
      `/api/v1/coach/assignments${studentId !== undefined ? `?student_id=${studentId}` : ""}`,
    ),
  createAssignment: (body: { student_id: number; exercise_slug: string; note?: string; due_at?: string }) =>
    request<Assignment>("/api/v1/coach/assignments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateAssignment: (id: number, status: string) =>
    request<Assignment>(`/api/v1/coach/assignments/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};

// Parent reads (active parent-student relationship required server-side).
// Assignment visibility is read-only; parents never manage assignments.
export const parentApi = {
  ...childrenReads("/api/v1/parent"),
};

// Administration transport (Phase 6). UX only — every endpoint
// authorizes server-side via canonical capabilities.
function adminQuery(params?: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
}

export const adminApi = {
  dashboard: () => request<AdminOverview>("/api/v1/admin/dashboard"),
  users: (params?: { search?: string; role?: string; status?: string; page?: number; page_size?: number }) =>
    request<AdminUser[]>(`/api/v1/admin/users${adminQuery(params)}`),
  user: (id: number) => request<AdminUserDetail>(`/api/v1/admin/users/${id}`),
  suspendUser: (id: number) =>
    request<AdminUser>(`/api/v1/admin/users/${id}/suspend`, { method: "POST" }),
  reactivateUser: (id: number) =>
    request<AdminUser>(`/api/v1/admin/users/${id}/reactivate`, { method: "POST" }),
  userRoles: (id: number) => request<{ roles: string[] }>(`/api/v1/admin/users/${id}/roles`),
  assignRole: (id: number, role: string) =>
    request<{ roles: string[] }>(`/api/v1/admin/users/${id}/roles`, {
      method: "POST",
      body: JSON.stringify({ role }),
    }),
  revokeRole: (id: number, role: string) =>
    request<{ roles: string[] }>(`/api/v1/admin/users/${id}/roles/${role}`, {
      method: "DELETE",
    }),
  exercises: (params?: { active?: boolean; low_supply?: boolean; needs_review?: boolean }) =>
    request<AdminExercise[]>(`/api/v1/admin/exercises${adminQuery(params)}`),
  exercise: (slug: string) => request<AdminExerciseDetail>(`/api/v1/admin/exercises/${slug}`),
  updateExercise: (
    slug: string,
    body: { title_fa?: string; title_en?: string; description?: string; sort_order?: number; is_active?: boolean },
  ) =>
    request<AdminExerciseDetail>(`/api/v1/admin/exercises/${slug}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  puzzles: (params?: { exercise?: string; status?: string; page?: number; page_size?: number }) =>
    request<AdminPuzzle[]>(`/api/v1/admin/puzzles${adminQuery(params)}`),
  puzzle: (id: number) => request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}`),
  createPuzzle: (body: {
    exercise_slug: string;
    fen?: string | null;
    position_json?: Record<string, unknown>;
    answer_json?: Record<string, unknown>;
    hint_json?: Record<string, unknown>;
    prompt_fa?: string;
    explanation?: string;
    initial_rating?: number;
  }) =>
    request<AdminPuzzle>("/api/v1/admin/puzzles", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updatePuzzle: (id: number, body: Record<string, unknown>) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  publishPuzzle: (id: number) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/publish`, { method: "POST" }),
  validatePuzzle: (id: number) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/validate`, { method: "POST" }),
  reviewPuzzle: (id: number, body: { decision: string; notes?: string }) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  approvePuzzle: (id: number) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/approve`, { method: "POST" }),
  puzzleHistory: (id: number) => request<PuzzleHistory>(`/api/v1/admin/puzzles/${id}/history`),
  retirePuzzle: (id: number) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/retire`, { method: "POST" }),
  generators: () => request<Generator[]>("/api/v1/admin/generators"),
  runGenerator: (
    code: string,
    body: { count: number; seed?: number; target_rating?: number; difficulty?: number; config?: Record<string, unknown> },
  ) =>
    request<GeneratorRun>(`/api/v1/admin/generators/${code}/runs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generatorRuns: (params?: { generator?: string; exercise?: string; status?: string; page?: number; page_size?: number }) =>
    request<GeneratorRun[]>(`/api/v1/admin/generator-runs${adminQuery(params)}`),
  generatorRun: (id: number) => request<GeneratorRun>(`/api/v1/admin/generator-runs/${id}`),
  cancelGeneratorRun: (id: number) =>
    request<GeneratorRun>(`/api/v1/admin/generator-runs/${id}/cancel`, { method: "POST" }),
  audit: (params?: { action?: string; target_type?: string; page?: number; page_size?: number }) =>
    request<AdminAuditRecord[]>(`/api/v1/admin/audit${adminQuery(params)}`),
  // Admin analytics (Phase 8). Aggregate read-only metrics; every
  // endpoint authorizes server-side via analytics.read_* capabilities.
  platformAnalytics: (params?: { period?: string; date_from?: string; date_to?: string }) =>
    request<AdminPlatformAnalytics>(`/api/v1/admin/analytics${adminQuery(params)}`),
  exerciseAnalytics: (params?: { period?: string; date_from?: string; date_to?: string }) =>
    request<AdminExerciseAnalytics[]>(`/api/v1/admin/analytics/exercises${adminQuery(params)}`),
  puzzleAnalytics: (params?: { period?: string; exercise?: string; page?: number; page_size?: number }) =>
    request<AdminPuzzleAnalytics[]>(`/api/v1/admin/analytics/puzzles${adminQuery(params)}`),
  // Staff support workflows (Phase 11). UX only — every endpoint
  // authorizes server-side via support.read/respond/close.
  supportTickets: (params?: { status?: string; category?: string; page?: number; page_size?: number }) =>
    request<SupportTicket[]>(`/api/v1/admin/support/tickets${adminQuery(params)}`),
  supportTicket: (id: number) => request<SupportTicket>(`/api/v1/admin/support/tickets/${id}`),
  respondSupport: (id: number, body: string) =>
    request<SupportMessage>(`/api/v1/admin/support/tickets/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
  closeSupport: (id: number) =>
    request<SupportTicket>(`/api/v1/admin/support/tickets/${id}/close`, { method: "POST" }),
  supportStats: () => request<import("./types").SupportStats>("/api/v1/admin/support/stats"),
  // Puzzle safety transitions (server-enforced lifecycle; only valid
  // transitions succeed).
  quarantinePuzzle: (id: number, reason?: string) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/quarantine`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  releasePuzzle: (id: number, reason?: string) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/release`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  rejectPuzzle: (id: number, reason?: string) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  restorePuzzle: (id: number, reason?: string) =>
    request<AdminPuzzle>(`/api/v1/admin/puzzles/${id}/restore`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
    }),
  // Operations: review queue, dashboard, analytics, sales, insights, health.
  reviewQueue: (params?: { exercise?: string; status?: string; page?: number; page_size?: number }) =>
    request<import("./types").ReviewQueueItem[]>(`/api/v1/admin/review-queue${adminQuery(params)}`),
  dashboardExtended: () =>
    request<import("./types").DashboardExtended>("/api/v1/admin/dashboard-extended"),
  retention: () => request<import("./types").RetentionData>("/api/v1/admin/analytics/retention"),
  learning: (days?: number) =>
    request<import("./types").LearningOverview>(
      `/api/v1/admin/analytics/learning${adminQuery(days ? { days } : undefined)}`,
    ),
  recommendationStats: (days?: number) =>
    request<import("./types").RecommendationOverview>(
      `/api/v1/admin/analytics/recommendations${adminQuery(days ? { days } : undefined)}`,
    ),
  salesOverview: () =>
    request<import("./types").SalesOverview>("/api/v1/admin/sales/overview"),
  insights: () => request<import("./types").ProductInsight[]>("/api/v1/admin/insights"),
  systemHealth: () => request<import("./types").SystemHealth>("/api/v1/admin/system/health"),
  auditDetail: (id: number) => request<AdminAuditRecord>(`/api/v1/admin/audit/${id}`),
  exerciseAnalyticsDetail: (slug: string, params?: { period?: string }) =>
    request<import("./types").AdminExerciseAnalyticsDetail>(
      `/api/v1/admin/analytics/exercises/${slug}${adminQuery(params)}`,
    ),
  puzzleAnalyticsDetail: (id: number, params?: { period?: string }) =>
    request<AdminPuzzleAnalytics>(
      `/api/v1/admin/analytics/puzzles/${id}${adminQuery(params)}`,
    ),
};

// Billing transport. UX only — plans display, coupon quotes come from
// the server, and access is enforced backend-side (never inferred here).
export const billingApi = {
  plans: () => request<BillingPlan[]>("/api/v1/billing/plans"),
  subscription: () => request<Subscription>("/api/v1/billing/me/subscription"),
  entitlements: () => request<Entitlements>("/api/v1/billing/me/entitlements"),
  validateCoupon: (body: { code: string; plan_code?: string }) =>
    request<CouponQuote>("/api/v1/billing/coupons/validate", {
      method: "POST",
      body: JSON.stringify({ plan_code: "premium", ...body }),
    }),
  redeemCoupon: (body: { code: string; plan_code?: string; idempotency_key?: string }) =>
    request<Redemption>("/api/v1/billing/coupons/redeem", {
      method: "POST",
      body: JSON.stringify({ plan_code: "premium", ...body }),
    }),
  touchAttribution: (body: {
    campaign_slug?: string;
    coupon_code?: string;
    landing_path?: string;
  }) =>
    request<void>("/api/v1/billing/me/attribution", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelSubscription: () =>
    request<Subscription>("/api/v1/billing/me/subscription/cancel", {
      method: "POST",
    }),
};

// Admin billing transport (billing.read / billing.manage capabilities).
export const adminBillingApi = {
  campaigns: () =>
    request<Array<{ slug: string; name_fa: string; source: string; medium: string; content: string; is_active: boolean }>>(
      "/api/v1/admin/billing/campaigns",
    ),
  createCampaign: (body: { slug: string; name_fa?: string; source?: string; medium?: string; content?: string }) =>
    request<{ slug: string }>("/api/v1/admin/billing/campaigns", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  coupons: () => request<import("./types").AdminCoupon[]>("/api/v1/admin/billing/coupons"),
  createCoupon: (body: Record<string, unknown>) =>
    request<import("./types").AdminCoupon>("/api/v1/admin/billing/coupons", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setCouponActive: (id: number, isActive: boolean) =>
    request<import("./types").AdminCoupon>(`/api/v1/admin/billing/coupons/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
  report: () => request<CampaignReport[]>("/api/v1/admin/billing/report"),
  redemptions: (params?: { status?: string; coupon_code?: string; page?: number; page_size?: number }) =>
    request<Redemption[]>(`/api/v1/admin/billing/redemptions${adminQuery(params)}`),
  subscriptions: (params?: { user_id?: number; status?: string; page?: number; page_size?: number }) =>
    request<Array<Subscription & { user_id: number }>>(`/api/v1/admin/billing/subscriptions${adminQuery(params)}`),
  payments: (params?: { status?: string; page?: number; page_size?: number }) =>
    request<Array<Record<string, unknown>>>(`/api/v1/admin/billing/payments${adminQuery(params)}`),
  plans: () => request<import("./types").AdminPlan[]>("/api/v1/admin/billing/plans"),
  setPlanActive: (code: string, isActive: boolean) =>
    request<import("./types").AdminPlan>(`/api/v1/admin/billing/plans/${code}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
  setPriceActive: (id: number, isActive: boolean) =>
    request<import("./types").AdminPrice>(`/api/v1/admin/billing/prices/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
  setCampaignActive: (slug: string, isActive: boolean) =>
    request<{ slug: string }>(`/api/v1/admin/billing/campaigns/${slug}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
  createPlan: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/v1/admin/billing/plans", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createPrice: (planCode: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/v1/admin/billing/plans/${planCode}/prices`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
