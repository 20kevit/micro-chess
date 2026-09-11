import { afterEach, describe, expect, it, vi } from "vitest";
import { api, coachApi, parentApi, relationshipsApi, clearToken } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("relationships transport", () => {
  it("creates an invitation by username without user ids", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1, status: "pending" }));
    vi.stubGlobal("fetch", fetchMock);
    await relationshipsApi.create({ kind: "coach", other_username: "student_a" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/relationships");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.other_username).toBe("student_a");
    expect("student_id" in body).toBe(false);
    expect("user_id" in body).toBe(false);
  });

  it("lists, accepts, and revokes relationships by id", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await relationshipsApi.list({ kind: "coach", status: "pending" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/relationships?kind=coach&status=pending");
    await relationshipsApi.accept(7);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/relationships/7/accept");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe("POST");
    await relationshipsApi.revoke(7);
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/relationships/7/revoke");
  });

  it("reads coach students through relationship-scoped routes", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await coachApi.students();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/coach/students");
    await coachApi.progress(3);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/coach/students/3/progress");
    await coachApi.analytics(3, { period: "30d" });
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/coach/students/3/analytics?period=30d");
  });

  it("manages coach assignments without client-computed results", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    await coachApi.createAssignment({ student_id: 3, exercise_slug: "pin", note: "daily" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/coach/assignments");
    const body = JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(body.student_id).toBe(3);
    expect("score" in body).toBe(false);
    await coachApi.updateAssignment(1, "completed");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/coach/assignments/1");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe("PATCH");
  });

  it("reads parent children through separate routes", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await parentApi.children();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/parent/children");
    await parentApi.progress(5);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/parent/children/5/progress");
    await parentApi.assignments(5);
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/parent/children/5/assignments");
  });

  it("reads and completes own assignments without user ids", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await api.myAssignments();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/assignments");
    const doneMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1, status: "completed" }));
    vi.stubGlobal("fetch", doneMock);
    await api.completeAssignment(1);
    expect(doneMock.mock.calls[0]?.[0]).toBe("/api/v1/me/assignments/1");
    const body = JSON.parse((doneMock.mock.calls[0]?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(body.status).toBe("completed");
  });
});
