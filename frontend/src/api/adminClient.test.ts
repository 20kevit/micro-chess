import { afterEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function makeFetchMock<T>(body: T) {
  return vi.fn(async (_url: string, _init?: RequestInit) => ok(body));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("admin transport", () => {
  it("fetches the dashboard overview", async () => {
    const fetchMock = makeFetchMock({ users_total: 3 });
    vi.stubGlobal("fetch", fetchMock);
    const data = await adminApi.dashboard();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/dashboard");
    expect(data.users_total).toBe(3);
  });

  it("builds user list queries with documented filters only", async () => {
    const fetchMock = makeFetchMock([]);
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.users({ search: "kid", role: "PLAYER", status: "active", page: 2, page_size: 25 });
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url.startsWith("/api/v1/admin/users?")).toBe(true);
    expect(url).toContain("search=kid");
    expect(url).toContain("role=PLAYER");
    expect(url).toContain("status=active");
    expect(url).toContain("page=2");
  });

  it("suspends and reactivates with POST", async () => {
    const fetchMock = makeFetchMock({ id: 5, is_active: false });
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.suspendUser(5);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/users/5/suspend");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    await adminApi.reactivateUser(5);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/users/5/reactivate");
  });

  it("assigns and revokes roles through the role endpoints", async () => {
    const fetchMock = makeFetchMock({ roles: ["PLAYER", "COACH"] });
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.assignRole(7, "COACH");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/users/7/roles");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ role: "COACH" });
    await adminApi.revokeRole(7, "COACH");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/users/7/roles/COACH");
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("DELETE");
  });

  it("toggles exercise availability with PATCH", async () => {
    const fetchMock = makeFetchMock({ slug: "pin", is_active: false });
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.updateExercise("pin", { is_active: false });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/exercises/pin");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("PATCH");
  });

  it("drives the puzzle lifecycle through dedicated endpoints", async () => {
    const fetchMock = makeFetchMock({ id: 9, status: "draft" });
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.createPuzzle({ exercise_slug: "pin", prompt_fa: "سوال" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/puzzles");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    await adminApi.publishPuzzle(9);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/puzzles/9/publish");
    await adminApi.retirePuzzle(9);
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/admin/puzzles/9/retire");
  });

  it("propagates authorization failures to the UI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (_url: string, _init?: RequestInit) =>
          new Response(JSON.stringify({ error: { code: "FORBIDDEN" }, detail: "forbidden" }), {
            status: 403,
          }),
      ),
    );
    const err = await adminApi.dashboard().catch((e: unknown) => e);
    expect((err as { status: number }).status).toBe(403);
  });
});
