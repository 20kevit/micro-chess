import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { SupportTicket } from "../api/types";
import { AdminSupportPage } from "./AdminSupportPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      supportTicketsPage: vi.fn(),
      supportTickets: vi.fn(),
      supportTicket: vi.fn(),
      respondSupport: vi.fn(),
      closeSupport: vi.fn(),
      reopenSupport: vi.fn(),
      supportStats: vi.fn(),
    },
  };
});

const mocked = vi.mocked(adminApi, true);
const ticket: SupportTicket = {
  id: 7,
  subject: "مشکل ورود",
  category: "account",
  status: "closed",
  created_at: "2026-09-20T10:00:00",
  updated_at: "2026-09-21T10:00:00",
  closed_at: "2026-09-21T10:00:00",
  user_id: 12,
  assigned_admin_id: null,
  messages: [{ id: 1, author: "user", body: "ورود انجام نمی‌شود", created_at: "2026-09-20T10:00:00" }],
};

beforeEach(() => {
  vi.resetAllMocks();
  mocked.supportTicketsPage.mockResolvedValue({ items: [ticket], total: 1 });
  mocked.supportTickets.mockResolvedValue([ticket]);
  mocked.supportTicket.mockResolvedValue(ticket);
  mocked.supportStats.mockResolvedValue({ open: 0, answered: 0, closed: 1, by_status: [], by_category: [] });
  window.confirm = vi.fn(() => true);
});

describe("P13 admin support", () => {
  it("uses total pagination, opens context, and reopens with confirmation", async () => {
    const actor = userEvent.setup();
    render(<MemoryRouter><AdminSupportPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("button", { name: /مشکل ورود/ })).toBeTruthy());
    expect(screen.getAllByText("بسته شد").length).toBeGreaterThan(0);
    expect(mocked.supportTicketsPage).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20 }));
    await actor.click(screen.getByRole("button", { name: /مشکل ورود/ }));
    await waitFor(() => expect(screen.getByText("ورود انجام نمی‌شود")).toBeTruthy());
    expect(screen.getAllByRole("link", { name: /زمینه کاربر/ })[0].getAttribute("href")).toBe("/admin/users/12");
    await actor.click(screen.getByRole("button", { name: "بازگشایی" }));
    await waitFor(() => expect(mocked.reopenSupport).toHaveBeenCalledWith(7));
  });
});
