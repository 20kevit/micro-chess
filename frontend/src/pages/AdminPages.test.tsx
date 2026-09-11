import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AuthUser } from "../api/types";
import { AppShell } from "../components/ui/AppShell";
import { useAuth } from "../lib/auth-context";
import { RequireAdmin } from "../lib/require-admin";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { AdminPuzzlesPage } from "./AdminPuzzlesPage";
import { AdminUsersPage } from "./AdminUsersPage";
import { LoginPage } from "./LoginPage";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      dashboard: vi.fn(),
      users: vi.fn(),
      user: vi.fn(),
      suspendUser: vi.fn(),
      reactivateUser: vi.fn(),
      userRoles: vi.fn(),
      assignRole: vi.fn(),
      revokeRole: vi.fn(),
      exercises: vi.fn(),
      exercise: vi.fn(),
      updateExercise: vi.fn(),
      puzzles: vi.fn(),
      puzzle: vi.fn(),
      createPuzzle: vi.fn(),
      updatePuzzle: vi.fn(),
      publishPuzzle: vi.fn(),
      retirePuzzle: vi.fn(),
      audit: vi.fn(),
    },
  };
});

const mockedUseAuth = vi.mocked(useAuth);
const mockedAdmin = vi.mocked(adminApi);

function base(overrides: object = {}) {
  return {
    user: null,
    loading: false,
    error: "",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ReturnType<typeof useAuth>;
}

const ADMIN: AuthUser = {
  id: 1,
  username: "boss",
  display_name: "boss",
  roles: ["PLAYER", "ADMIN"],
  created_at: "2026-01-01T00:00:00",
};

const PLAYER: AuthUser = {
  id: 2,
  username: "kid",
  display_name: "kid",
  roles: ["PLAYER"],
  created_at: "2026-01-01T00:00:00",
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("admin route guard (UX only)", () => {
  it("redirects anonymous visitors to login", async () => {
    mockedUseAuth.mockReturnValue(base({ user: null }));
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminDashboardPage />
              </RequireAdmin>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("ورود به میکروچس")).toBeTruthy());
  });

  it("blocks non-admin users with a Persian message", () => {
    mockedUseAuth.mockReturnValue(base({ user: PLAYER }));
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminDashboardPage />
              </RequireAdmin>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("به بخش مدیریت دسترسی نداری.")).toBeTruthy();
  });

  it("renders the dashboard for admins", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.dashboard.mockResolvedValue({
      users_total: 2,
      users_active: 2,
      users_suspended: 0,
      exercises_total: 1,
      exercises_active: 1,
      puzzles_total: 1,
      puzzles_published: 1,
      puzzles_archived: 0,
      attempts_total: 0,
      attempts_last_24h: 0,
      recent_registrations: [],
      recent_audit: [],
    });
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminDashboardPage />
              </RequireAdmin>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("مدیریت")).toBeTruthy());
    expect(screen.getByText("هنوز رویداد مدیریتی ثبت نشده است.")).toBeTruthy();
  });
});

describe("admin dashboard states", () => {
  it("shows loading, then an error with retry", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.dashboard.mockRejectedValue(new Error("api_error:500"));
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <AdminDashboardPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    expect(screen.getByText("تلاش دوباره")).toBeTruthy();
  });
});

describe("admin users page", () => {
  it("shows the empty state in Persian", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.users.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/users"]}>
        <AdminUsersPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("کاربری پیدا نشد.")).toBeTruthy());
  });

  it("lists users with status badges", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.users.mockResolvedValue([
      { id: 1, username: "boss", display_name: "boss", roles: ["ADMIN"], is_active: true, created_at: "" },
      { id: 2, username: "kid", display_name: "kid", roles: ["PLAYER"], is_active: false, created_at: "" },
    ]);
    render(
      <MemoryRouter initialEntries={["/admin/users"]}>
        <AdminUsersPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("boss")).toBeTruthy());
    // Each status word appears once in the filter <select> and once per
    // matching badge, so both must be present at least twice.
    expect(screen.getAllByText("فعال").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("تعلیق‌شده").length).toBeGreaterThanOrEqual(2);
  });
});

describe("admin puzzles page", () => {
  it("shows the empty state and the draft form", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.puzzles.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("موردی نیست.")).toBeTruthy());
    expect(screen.getByText("ساخت پیش‌نویس")).toBeTruthy();
  });
});

describe("admin navigation", () => {
  it("hides the admin tab from players and shows it to admins", () => {
    mockedUseAuth.mockReturnValue(base({ user: PLAYER }));
    const { unmount } = render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.queryByText("مدیریت")).toBeNull();
    unmount();

    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.getByText("مدیریت")).toBeTruthy();
  });
});
