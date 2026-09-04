// Thin HTTP client. Backend is authoritative; this only transports data.
import type { AttemptMode, AttemptResponse, Exercise, Puzzle } from "./types";

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
  submitAttempt: (body: { puzzle_id: number; answer: Record<string, unknown>; mode: AttemptMode }) =>
    request<AttemptResponse>("/api/v1/attempts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
