import { afterEach, describe, expect, it, vi } from "vitest";
import { api, clearToken } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("player platform transport", () => {
  it("updates the profile with PATCH and no user id", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ display_name: "Omid" }));
    vi.stubGlobal("fetch", fetchMock);
    await api.updateProfile({ display_name: "Omid", bio: "x" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/profile");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PATCH");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.display_name).toBe("Omid");
    expect("user_id" in body).toBe(false);
  });

  it("builds the history query string from filters", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await api.trainingAttempts({ exercise: "pin", mode: "practice", correct: true, page: 2, page_size: 20 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/me/training/attempts?exercise=pin&mode=practice&correct=true&page=2&page_size=20",
    );
  });

  it("requests history without a query string when unfiltered", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await api.trainingAttempts();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/training/attempts");
  });

  it("adds and removes chess identities", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.addIdentity({ provider: "lichess", username: "omid", rating: 1500 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/chess-identities");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("POST");

    const deleteMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", deleteMock);
    await api.deleteIdentity(1);
    expect(deleteMock.mock.calls[0]?.[0]).toBe("/api/v1/me/chess-identities/1");
    expect((deleteMock.mock.calls[0]?.[1] as RequestInit).method).toBe("DELETE");
  });

  it("fetches ratings without sending user ids", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await api.getRatings();
    await api.getExerciseRating("pin");
    await api.getRatingHistory("pin");
    const calls = fetchMock.mock.calls.map((call) => call[0]);
    expect(calls).toEqual([
      "/api/v1/me/ratings",
      "/api/v1/me/ratings/pin",
      "/api/v1/me/ratings/pin/history",
    ]);
    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit | undefined;
      expect(init?.method ?? "GET").toBe("GET");
      expect(String(call[0])).not.toContain("user_id");
    }
  });

  it("fetches progress, dashboard, and exercise detail", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({}));
    vi.stubGlobal("fetch", fetchMock);
    await api.progress();
    await api.dashboard();
    await api.exerciseDetail("pin");
    const urls = fetchMock.mock.calls.map((call) => call[0]);
    expect(urls).toEqual([
      "/api/v1/me/progress",
      "/api/v1/me/dashboard",
      "/api/v1/exercises/pin",
    ]);
  });
});
