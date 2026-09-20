import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";
import { AppShell } from "../components/ui/AppShell";
import { useAuth } from "../lib/auth-context";
import { api, notificationsApi } from "../api/client";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/client", () => ({
  api: {
    dashboard: vi.fn(),
    progress: vi.fn(),
    trainingAttempts: vi.fn(),
  },
  // AppShell fetches the unread badge through this transport.
  notificationsApi: {
    unreadCount: vi.fn().mockResolvedValue({ unread_count: 0 }),
  },
  apiStatus: () => null,
  getToken: () => null,
  setToken: vi.fn(),
  clearToken: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedApi = vi.mocked(api, true);

function authState(user: boolean) {
  mockedUseAuth.mockReturnValue({
    user: user
      ? { id: 1, username: "kid_01", display_name: "kid_01", roles: ["PLAYER"], active_role: "PLAYER", created_at: "" }
      : null,
    loading: false,
    error: "",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    switchRole: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
  } as ReturnType<typeof useAuth>);
}

beforeEach(() => {
  vi.resetAllMocks();
  // AppShell reads the unread badge through this transport.
  vi.mocked(notificationsApi.unreadCount).mockResolvedValue({ unread_count: 0 });
});

describe("player home", () => {
  it("shows the parent-focused landing (not the exercise catalog) to anonymous visitors", () => {
    authState(false);
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "شطرنج را متفاوت تمرین کن!" })).toBeTruthy();
    expect(screen.queryByText(/سلام!/)).toBeNull();
  });

  it("onboards anonymous visitors with a recommendation CTA into registration", () => {
    authState(false);
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    const ctas = screen.getAllByRole("link", { name: "دریافت بسته‌ی تمرین پیشنهادی" });
    expect(ctas.length).toBeGreaterThan(0);
    for (const cta of ctas) expect(cta.getAttribute("href")).toBe("/register");
    const logins = screen.getAllByRole("link", { name: "ورود به حساب" });
    expect(logins.length).toBeGreaterThan(0);
    for (const login of logins) expect(login.getAttribute("href")).toBe("/login");
  });

  it("shows the dashboard to authenticated players", async () => {
    authState(true);
    mockedApi.dashboard.mockResolvedValue({
      profile: { display_name: "kid_01", bio: "", avatar_reference: "", updated_at: null },
      progress: { attempts: 0, correct: 0, accuracy: 0, exercises: [] },
      recent_attempts: [],
    });
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("هنوز تمرینی انجام نداده‌ای.")).toBeTruthy());
    expect(mockedApi.dashboard).toHaveBeenCalled();
  });

  it("shows four nav tabs for players and two for guests", () => {
    authState(true);
    const { unmount } = render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.getByText("پیشرفت")).toBeTruthy();
    expect(screen.getByText("پروفایل")).toBeTruthy();
    unmount();

    authState(false);
    render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.queryByText("پیشرفت")).toBeNull();
    expect(screen.queryByText("پروفایل")).toBeNull();
  });
});
