import { afterEach, describe, expect, it, vi } from "vitest";
import { api, clearToken, coachApi, parentApi } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("adaptive training transport", () => {
  it("fetches overview/next/history without sending ratings or scores", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({}));
    vi.stubGlobal("fetch", fetchMock);
    await api.adaptiveOverview();
    await api.adaptiveNext("piece-recognition");
    await api.adaptiveHistory();
    const calls = fetchMock.mock.calls.map((call) => call[0]);
    expect(calls).toEqual([
      "/api/v1/me/adaptive/overview",
      "/api/v1/me/adaptive/next?exercise=piece-recognition",
      "/api/v1/me/adaptive/history",
    ]);
    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit | undefined;
      expect(init?.method ?? "GET").toBe("GET");
      expect(String(call[0])).not.toContain("user_id");
      expect(String(call[0])).not.toContain("rating");
      expect(String(call[0])).not.toContain("score");
    }
  });

  it("records outcomes with POST and no authoritative values", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 3 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.adaptiveOutcome(3, { status: "accepted" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/adaptive/outcomes/3");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.status).toBe("accepted");
    expect("rating" in body).toBe(false);
    expect("score" in body).toBe(false);
    expect("user_id" in body).toBe(false);
  });

  it("reads authorized student adaptive overviews on scoped paths", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({}));
    vi.stubGlobal("fetch", fetchMock);
    await coachApi.adaptive(9);
    await parentApi.adaptive(9);
    const calls = fetchMock.mock.calls.map((call) => call[0]);
    expect(calls).toEqual([
      "/api/v1/coach/students/9/adaptive/overview",
      "/api/v1/parent/children/9/adaptive/overview",
    ]);
  });
});
