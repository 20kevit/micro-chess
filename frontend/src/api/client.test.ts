import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  apiCode,
  apiDetail,
  apiDetails,
  apiRoles,
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

describe("active-role transport", () => {
  it("parses structured error details and role lists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        fail(409, {
          error: { code: "ROLE_SELECTION_REQUIRED", details: { roles: ["PLAYER", "COACH"] } },
          detail: "role_selection_required",
        }),
      ),
    );
    const err = await api.me().catch((e: unknown) => e);
    expect(apiStatus(err)).toBe(409);
    expect(apiCode(err)).toBe("ROLE_SELECTION_REQUIRED");
    expect(apiDetails(err)).toEqual({ roles: ["PLAYER", "COACH"] });
    expect(apiRoles(err)).toEqual(["PLAYER", "COACH"]);
  });

  it("returns an empty role list when details carry none", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => fail(401, { detail: "auth_required" })));
    const err = await api.me().catch((e: unknown) => e);
    expect(apiRoles(err)).toEqual([]);
  });

  it("sends the selected role on login", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ access_token: "t", token_type: "bearer" }));
    vi.stubGlobal("fetch", fetchMock);
    await api.login({ username: "kid_01", password: "secret123", role: "COACH" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/login");
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toEqual({
      username: "kid_01",
      password: "secret123",
      role: "COACH",
    });
  });

  it("switches the session role through the dedicated endpoint", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      ok({ active_role: "PLAYER", roles: ["PLAYER", "COACH"] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const out = await api.switchActiveRole("PLAYER");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/active-role");
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toEqual({ role: "PLAYER" });
    expect(out).toEqual({ active_role: "PLAYER", roles: ["PLAYER", "COACH"] });
  });
});
