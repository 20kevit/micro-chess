import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";
import { AppShell } from "../components/ui/AppShell";
import { useAuth } from "../lib/auth-context";
import { journeyApi, notificationsApi, onboardingApi, quotaApi } from "../api/client";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/client", () => ({
  api: {
    dashboard: vi.fn(),
    progress: vi.fn(),
    trainingAttempts: vi.fn(),
  },
  onboardingApi: {
    get: vi.fn(),
  },
  journeyApi: {
    today: vi.fn(),
    startQuest: vi.fn(),
    completeQuest: vi.fn(),
  },
  quotaApi: {
    get: vi.fn(),
  },
  notifyApi: {
    track: vi.fn().mockResolvedValue(undefined),
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
  vi.mocked(quotaApi.get).mockResolvedValue({
    used: 0, limit: 10, remaining: 10, plan: "free", local_date: "",
    can_practice: true, upgrade_available: true,
  });
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

  it("shows the daily journey to onboarded players (verification never gates free use)", async () => {
    authState(true);
    vi.mocked(onboardingApi.get).mockResolvedValue({
      experience: "beginner",
      play_frequency: "weekly",
      fide_rating: null,
      lichess_username: "",
      chesscom_username: "",
      goal: "improve",
      intensity: "standard",
      timezone: "Asia/Tehran",
      onboarding_completed: true,
      placement_completed: true,
    });
    vi.mocked(journeyApi.today).mockResolvedValue({
      local_date: "2026-09-21",
      timezone: "Asia/Tehran",
      completed_count: 0,
      total: 3,
      is_complete: false,
      quests: [],
    });
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("امروز ۳ مأموریت برایت آماده کرده‌ایم.")).toBeTruthy());
    expect(onboardingApi.get).toHaveBeenCalled();
  });

  it("gates incomplete onboarding to the onboarding flow", async () => {
    authState(true);
    vi.mocked(onboardingApi.get).mockResolvedValue({
      experience: "",
      play_frequency: "",
      fide_rating: null,
      lichess_username: "",
      chesscom_username: "",
      goal: "",
      intensity: "standard",
      timezone: "Asia/Tehran",
      onboarding_completed: false,
      placement_completed: false,
    });
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("سطحت در شطرنج چطوره؟")).toBeTruthy());
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
