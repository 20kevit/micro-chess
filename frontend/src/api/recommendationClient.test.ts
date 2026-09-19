import { afterEach, describe, expect, it, vi } from "vitest";
import { api, clearToken } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("recommendation transport", () => {
  it("fetches the recommendation with GET and no user-supplied values", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok(null));
    vi.stubGlobal("fetch", fetchMock);
    await api.recommendation();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/recommendations");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(init?.method ?? "GET").toBe("GET");
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("user_id");
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("trace");
    expect(init?.body).toBeUndefined();
  });
});
