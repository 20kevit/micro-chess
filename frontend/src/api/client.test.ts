import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  apiCode,
  apiDetail,
  apiStatus,
  clearToken,
  getToken,
  setToken,
} from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function fail(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("auth token transport", () => {
  it("stores and clears the token", () => {
    expect(getToken()).toBeNull();
    setToken("abc");
    expect(getToken()).toBe("abc");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("sends the bearer token when present", async () => {
    setToken("tok123");
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.me();
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBe("Bearer tok123");
  });

  it("omits the authorization header anonymously", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await api.listExercises();
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBeUndefined();
  });
});

describe("error envelope", () => {
  it("parses the new error.code alongside legacy detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => fail(404, { error: { code: "PUZZLE_NOT_AVAILABLE" }, detail: "puzzle_not_available" })),
    );
    const err = await api.me().catch((e: unknown) => e);
    expect(apiStatus(err)).toBe(404);
    expect(apiCode(err)).toBe("PUZZLE_NOT_AVAILABLE");
    expect(apiDetail(err)).toBe("puzzle_not_available");
    expect((err as Error).message).toBe("api_error:404:puzzle_not_available");
  });

  it("supports legacy detail-only bodies", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => fail(401, { detail: "auth_required" })));
    const err = await api.me().catch((e: unknown) => e);
    expect(apiStatus(err)).toBe(401);
    expect(apiCode(err)).toBe("");
    expect(apiDetail(err)).toBe("auth_required");
  });

  it("survives non-JSON error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 })));
    const err = await api.me().catch((e: unknown) => e);
    expect(apiStatus(err)).toBe(502);
    expect(apiCode(err)).toBe("");
  });

  it("resolves 204 responses without a body", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    await expect(api.logout()).resolves.toBeUndefined();
  });
});
