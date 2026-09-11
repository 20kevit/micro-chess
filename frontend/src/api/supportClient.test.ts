import { afterEach, describe, expect, it, vi } from "vitest";
import { adminApi, clearToken, notificationsApi, supportApi } from "./client";

function ok<T>(body: T): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("support & notification transport", () => {
  it("creates support tickets without client-owned identity fields", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok({ id: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    await supportApi.create({ subject: "login issue", message: "help me" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/support/tickets");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.subject).toBe("login issue");
    expect("user_id" in body).toBe(false);
    expect("owner_id" in body).toBe(false);
    expect("status" in body).toBe(false);
  });

  it("reads and replies to own tickets through /me routes", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await supportApi.myTickets({ status: "open", page: 1, page_size: 20 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/me/support/tickets?status=open&page=1&page_size=20",
    );
    await supportApi.myTicket(4);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/me/support/tickets/4");
    await supportApi.reply(4, "more detail");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/me/support/tickets/4/messages");
    expect((fetchMock.mock.calls[2]?.[1] as RequestInit).method).toBe("POST");
  });

  it("lists notifications, counts unread, marks read, and edits preferences", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await notificationsApi.list({ unread_only: true });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/notifications?unread_only=true");
    await notificationsApi.unreadCount();
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/me/notifications/unread-count");
    await notificationsApi.markRead(9);
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/me/notifications/9/read");
    expect((fetchMock.mock.calls[2]?.[1] as RequestInit).method).toBe("POST");
    await notificationsApi.preferences();
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/v1/me/notification-preferences");
    await notificationsApi.updatePreference({ category: "support", channel: "in_app", enabled: false });
    expect(fetchMock.mock.calls[4]?.[0]).toBe("/api/v1/me/notification-preferences");
    expect((fetchMock.mock.calls[4]?.[1] as RequestInit).method).toBe("PATCH");
  });

  it("runs staff support workflows through admin routes", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ok([]));
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.supportTickets({ status: "open" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/support/tickets?status=open");
    await adminApi.supportTicket(5);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/support/tickets/5");
    await adminApi.respondSupport(5, "try again");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/admin/support/tickets/5/messages");
    await adminApi.closeSupport(5);
    expect(fetchMock.mock.calls[3]?.[0]).toBe("/api/v1/admin/support/tickets/5/close");
    expect((fetchMock.mock.calls[3]?.[1] as RequestInit).method).toBe("POST");
  });
});
