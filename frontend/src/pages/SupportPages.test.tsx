import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SupportDetailPage } from "./SupportDetailPage";
import { SupportPage } from "./SupportPage";
import { supportApi } from "../api/client";
import type { SupportTicket } from "../api/types";
import { t } from "../i18n";

vi.mock("../api/client", () => ({
  supportApi: { create: vi.fn(), myTickets: vi.fn(), myTicket: vi.fn(), reply: vi.fn() },
  apiDetail: () => "",
  apiStatus: () => null,
}));

const mocked = vi.mocked(supportApi, true);

const openTicket: SupportTicket = {
  id: 3,
  subject: "Login problem",
  category: "",
  status: "open",
  created_at: "",
  updated_at: "",
  closed_at: null,
};

const closedTicket: SupportTicket = {
  ...openTicket,
  id: 4,
  status: "closed",
  closed_at: "",
  messages: [{ id: 1, author: "user", body: "help", created_at: "" }],
};

beforeEach(() => {
  vi.resetAllMocks();
});

function renderList() {
  render(
    <MemoryRouter>
      <SupportPage />
    </MemoryRouter>,
  );
}

function renderDetail() {
  render(
    <MemoryRouter initialEntries={["/support/4"]}>
      <Routes>
        <Route path="/support/:id" element={<SupportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("support pages", () => {
  it("renders the Persian form, creates a ticket, and lists it", async () => {
    mocked.myTickets.mockResolvedValue([openTicket]);
    mocked.create.mockResolvedValue({ ...openTicket, messages: [] });
    renderList();
    await waitFor(() => expect(screen.getByText(t("support.title"))).toBeTruthy());
    expect(screen.getByText(t("support.newTitle"))).toBeTruthy();

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(t("support.subjectPlaceholder")), "Login problem");
    await user.type(screen.getByPlaceholderText(t("support.messagePlaceholder")), "help me");
    await user.click(screen.getByRole("button", { name: t("support.send") }));
    await waitFor(() => expect(mocked.create).toHaveBeenCalled());
    expect(mocked.create.mock.calls[0]?.[0]).toEqual({
      subject: "Login problem",
      message: "help me",
    });
    expect(screen.getByText("Login problem")).toBeTruthy();
    expect(screen.getByText(t("support.open"))).toBeTruthy();
  });

  it("shows loading, empty, and error states", async () => {
    mocked.myTickets.mockImplementation(() => new Promise(() => {}));
    renderList();
    expect(screen.getByText(t("common.loading"))).toBeTruthy();

    mocked.myTickets.mockResolvedValue([]);
    renderList();
    await waitFor(() => expect(screen.getByText(t("support.empty"))).toBeTruthy());

    mocked.myTickets.mockRejectedValue(new Error("down"));
    renderList();
    await waitFor(() => expect(screen.getByText(t("common.error"))).toBeTruthy());
  });

  it("shows the conversation and hides the reply box once closed", async () => {
    mocked.myTicket.mockResolvedValue(closedTicket);
    renderDetail();
    await waitFor(() => expect(screen.getByText("Login problem")).toBeTruthy());
    expect(screen.getByText("help")).toBeTruthy();
    expect(screen.getByText(t("support.closedNote"))).toBeTruthy();
    expect(screen.queryByPlaceholderText(t("support.replyPlaceholder"))).toBeNull();
  });

  it("sends an owner reply on open tickets", async () => {
    mocked.myTicket.mockResolvedValue({
      ...openTicket,
      messages: [{ id: 1, author: "staff", body: "hi", created_at: "" }],
    });
    mocked.reply.mockResolvedValue({ id: 2, author: "user", body: "thanks", created_at: "" });
    render(
      <MemoryRouter initialEntries={["/support/3"]}>
        <Routes>
          <Route path="/support/:id" element={<SupportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("hi")).toBeTruthy());
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(t("support.replyPlaceholder")), "thanks");
    await user.click(screen.getByRole("button", { name: t("support.reply") }));
    await waitFor(() => expect(mocked.reply).toHaveBeenCalledWith(3, "thanks"));
  });
});
