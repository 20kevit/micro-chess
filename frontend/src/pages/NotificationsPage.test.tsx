import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationsPage } from "./NotificationsPage";
import { notificationsApi } from "../api/client";
import type { NotificationItem, NotificationPreference } from "../api/types";
import { t } from "../i18n";

vi.mock("../api/client", () => ({
  notificationsApi: {
    list: vi.fn(),
    unreadCount: vi.fn(),
    markRead: vi.fn(),
    preferences: vi.fn(),
    updatePreference: vi.fn(),
  },
  apiDetail: () => "",
}));

const mocked = vi.mocked(notificationsApi, true);

const unread: NotificationItem = {
  id: 1,
  type: "support.response",
  category: "support",
  title: "Login problem",
  body: "try resetting",
  read_at: null,
  created_at: "",
};

const read: NotificationItem = {
  id: 2,
  type: "account.reactivated",
  category: "account",
  title: "account.reactivated",
  body: "",
  read_at: "2026-01-01",
  created_at: "",
};

const prefs: NotificationPreference[] = [
  { category: "support", channel: "in_app", enabled: true, mandatory: false },
  { category: "account", channel: "in_app", enabled: true, mandatory: true },
];

beforeEach(() => {
  vi.resetAllMocks();
  mocked.list.mockResolvedValue([unread, read]);
  mocked.preferences.mockResolvedValue(prefs);
});

function renderPage() {
  render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>,
  );
}

describe("notifications page", () => {
  it("renders Persian titles, unread items, and preference controls", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(t("notif.title"))).toBeTruthy());
    expect(screen.getByText(t("notif.type.support.response"))).toBeTruthy();
    expect(screen.getByText(t("notif.type.account.reactivated"))).toBeTruthy();
    expect(screen.getByText(t("notif.prefsTitle"))).toBeTruthy();
    expect(screen.getByText(t("notif.support"))).toBeTruthy();
    expect(screen.getByText(t("notif.mandatory"), { exact: false })).toBeTruthy();
  });

  it("marks a notification read and filters unread", async () => {
    mocked.markRead.mockResolvedValue({ ...unread, read_at: "2026-01-02" });
    renderPage();
    await waitFor(() => expect(screen.getByText(t("notif.title"))).toBeTruthy());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: t("notif.markRead") }));
    await waitFor(() => expect(mocked.markRead).toHaveBeenCalledWith(1));

    await user.click(screen.getByRole("checkbox", { name: t("notif.unreadOnly") }));
    await waitFor(() => expect(mocked.list).toHaveBeenCalledWith({ unread_only: true }));
  });

  it("toggles optional preferences but never mandatory ones", async () => {
    mocked.updatePreference.mockResolvedValue({ ...prefs[0], enabled: false });
    renderPage();
    await waitFor(() => expect(screen.getByText(t("notif.prefsTitle"))).toBeTruthy());

    const user = userEvent.setup();
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(2);
    // Mandatory account switch is disabled.
    expect(switches[1].getAttribute("disabled")).not.toBeNull();
    await user.click(switches[0]);
    await waitFor(() => expect(mocked.updatePreference).toHaveBeenCalledWith({
      category: "support",
      channel: "in_app",
      enabled: false,
    }));
  });

  it("shows loading, empty, and error states", async () => {
    mocked.list.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText(t("common.loading"))).toBeTruthy();

    mocked.list.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(t("notif.empty"))).toBeTruthy());

    mocked.list.mockRejectedValue(new Error("down"));
    renderPage();
    await waitFor(() => expect(screen.getByText(t("common.error"))).toBeTruthy());
  });
});
