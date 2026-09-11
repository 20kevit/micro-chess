import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminSupportPage } from "./AdminSupportPage";
import { adminApi } from "../api/client";
import type { SupportTicket } from "../api/types";
import { t } from "../i18n";

vi.mock("../api/client", () => ({
  adminApi: {
    supportTickets: vi.fn(),
    supportTicket: vi.fn(),
    respondSupport: vi.fn(),
    closeSupport: vi.fn(),
  },
  apiDetail: () => "",
}));

const mocked = vi.mocked(adminApi, true);

const ticket: SupportTicket = {
  id: 7,
  subject: "Login problem",
  category: "",
  status: "open",
  created_at: "",
  updated_at: "",
  closed_at: null,
  user_id: 11,
  assigned_admin_id: null,
  messages: [{ id: 1, author: "user", body: "help", created_at: "" }],
};

beforeEach(() => {
  vi.resetAllMocks();
  mocked.supportTickets.mockResolvedValue([ticket]);
  mocked.supportTicket.mockResolvedValue(ticket);
});

function renderPage() {
  render(
    <MemoryRouter>
      <AdminSupportPage />
    </MemoryRouter>,
  );
}

describe("admin support page", () => {
  it("lists tickets, opens the conversation, responds, and closes", async () => {
    mocked.respondSupport.mockResolvedValue({ id: 2, author: "staff", body: "hi", created_at: "" });
    mocked.closeSupport.mockResolvedValue({ ...ticket, status: "closed" });
    renderPage();
    await waitFor(() => expect(screen.getByText(t("admin.support"))).toBeTruthy());
    expect(screen.getByText("Login problem")).toBeTruthy();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Login problem/ }));
    await waitFor(() => expect(mocked.supportTicket).toHaveBeenCalledWith(7));
    expect(screen.getByText("help")).toBeTruthy();

    await user.type(screen.getByLabelText(t("admin.supportRespond")), "hi");
    await user.click(screen.getByRole("button", { name: t("admin.supportRespond") }));
    await waitFor(() => expect(mocked.respondSupport).toHaveBeenCalledWith(7, "hi"));

    window.confirm = vi.fn(() => true);
    await user.click(screen.getByRole("button", { name: t("admin.supportClose") }));
    await waitFor(() => expect(mocked.closeSupport).toHaveBeenCalledWith(7));
  });

  it("filters by status and shows the empty state", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(t("admin.support"))).toBeTruthy());
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText(t("admin.supportFilter")), "closed");
    await waitFor(() =>
      expect(mocked.supportTickets).toHaveBeenCalledWith({ status: "closed" }),
    );

    mocked.supportTickets.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(t("admin.supportEmpty"))).toBeTruthy());
  });
});
