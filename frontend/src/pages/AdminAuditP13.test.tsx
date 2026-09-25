import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminAuditRecord } from "../api/types";
import { AdminAuditPage } from "./AdminAuditPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      auditPage: vi.fn(),
      audit: vi.fn(),
    },
  };
});

const mocked = vi.mocked(adminApi, true);
const record: AdminAuditRecord = {
  id: 4,
  actor_user_id: 2,
  action: "users.suspend",
  target_type: "user",
  target_id: "9",
  metadata: { username: "kid", reason: "manual" },
  result: "ok",
  created_at: "2026-09-20T12:00:00",
};

beforeEach(() => {
  vi.resetAllMocks();
  mocked.auditPage.mockResolvedValue({ items: [record], total: 1 });
  mocked.audit.mockResolvedValue([record]);
});

describe("P13 admin audit", () => {
  it("renders localized actor, object, result, and structured metadata", async () => {
    const actor = userEvent.setup();
    render(<MemoryRouter><AdminAuditPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("گزارش حسابرسی")).toBeTruthy());
    expect(screen.getByText("تعلیق")).toBeTruthy();
    expect(screen.getAllByText("کاربر").length).toBeGreaterThan(0);
    expect(screen.getByText("تأییدشده")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("{\"username\"");
    await actor.type(screen.getByLabelText("نوع موضوع"), "user");
    await waitFor(() => expect(mocked.auditPage).toHaveBeenCalledWith(expect.objectContaining({ target_type: "user", page: 1, page_size: 20 })));
  });
});
