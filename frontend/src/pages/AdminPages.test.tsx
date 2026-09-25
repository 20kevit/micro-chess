import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AuthUser } from "../api/types";
import { AppShell } from "../components/ui/AppShell";
import { useAuth } from "../lib/auth-context";
import { RequireAdmin } from "../lib/require-admin";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { AdminGeneratorsPage } from "./AdminGeneratorsPage";
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
      validatePuzzle: vi.fn(),
      reviewPuzzle: vi.fn(),
      approvePuzzle: vi.fn(),
      puzzleHistory: vi.fn(),
      puzzleUsage: vi.fn(),
      previewValidate: vi.fn(),
      bulkPuzzles: vi.fn(),
      publishPuzzle: vi.fn(),
      retirePuzzle: vi.fn(),
      quarantinePuzzle: vi.fn(),
      releasePuzzle: vi.fn(),
      rejectPuzzle: vi.fn(),
      restorePuzzle: vi.fn(),
      createExercise: vi.fn(),
      answerContract: vi.fn(),
      exerciseQuality: vi.fn(),
      exerciseLearning: vi.fn(),
      exerciseGenerators: vi.fn(),
      contentHealth: vi.fn(),
      generators: vi.fn(),
      runGenerator: vi.fn(),
      generatorRuns: vi.fn(),
      generatorRun: vi.fn(),
      cancelGeneratorRun: vi.fn(),
      audit: vi.fn(),
      platformAnalytics: vi.fn(),
      exerciseAnalytics: vi.fn(),
      puzzleAnalytics: vi.fn(),
      supportStats: vi.fn(),
      reviewQueue: vi.fn(),
      dashboardExtended: vi.fn(),
      retention: vi.fn(),
      learning: vi.fn(),
      recommendationStats: vi.fn(),
      salesOverview: vi.fn(),
      insights: vi.fn(),
      systemHealth: vi.fn(),
      supportTickets: vi.fn(),
      supportTicket: vi.fn(),
      respondSupport: vi.fn(),
      closeSupport: vi.fn(),
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
    switchRole: vi.fn().mockResolvedValue(undefined),
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
  active_role: "ADMIN",
  created_at: "2026-01-01T00:00:00",
};

const PLAYER: AuthUser = {
  id: 2,
  username: "kid",
  display_name: "kid",
  roles: ["PLAYER"],
  active_role: "PLAYER",
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
    mockedAdmin.dashboardExtended.mockRejectedValue(new Error("no-extended"));
    mockedAdmin.insights.mockResolvedValue([]);
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
    mockedAdmin.dashboardExtended.mockRejectedValue(new Error("no-extended"));
    mockedAdmin.insights.mockResolvedValue([]);
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
      { id: 1, username: "boss", display_name: "boss", roles: ["ADMIN"], is_active: true, created_at: "",
        current_plan_code: null, current_plan_status: null, verification_channel: null, phone_verified: false, last_active_at: null,
        attempts_count: 0, coupon_redemption_count: 0 },
      { id: 2, username: "kid", display_name: "kid", roles: ["PLAYER"], is_active: false, created_at: "",
        current_plan_code: "free", current_plan_status: "active", verification_channel: "bale", phone_verified: true, last_active_at: null,
        attempts_count: 4, coupon_redemption_count: 1 },
    ]);
    render(
      <MemoryRouter initialEntries={["/admin/users"]}>
        <AdminUsersPage />
      </MemoryRouter>,
    );
     await waitFor(() => expect(screen.getAllByText("boss").length).toBeGreaterThanOrEqual(1));
    // Each status word appears once in the filter <select> and once per
    // matching badge, so both must be present at least twice.
    expect(screen.getAllByText("فعال").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("تعلیق‌شده").length).toBeGreaterThanOrEqual(2);
  });
});

describe("admin puzzles page", () => {
  it("shows the empty state and the authoring entry", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.puzzles.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("موردی نیست.")).toBeTruthy());
    expect(screen.getByText("افزودن معمای جدید")).toBeTruthy();
  });

  it("lists puzzles with filters and detail links", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.puzzles.mockResolvedValue([
      {
        id: 1, exercise_slug: "pin", status: "draft", fen: null, position_json: {},
        answer_json: {}, hint_json: {}, prompt_fa: "", explanation: "",
        initial_rating: 1200, is_published: false, is_archived: false,
        published_at: null, created_at: "", source: "manual", source_reference: null,
        generator_run_id: null, difficulty: null, target_rating: null, retired_at: null,
      },
      {
        id: 2, exercise_slug: "pin", status: "validated", fen: null, position_json: {},
        answer_json: {}, hint_json: {}, prompt_fa: "", explanation: "",
        initial_rating: 1200, is_published: false, is_archived: false,
        published_at: null, created_at: "", source: "generated", source_reference: null,
        generator_run_id: 3, difficulty: 2, target_rating: 950, retired_at: null,
      },
      {
        id: 3, exercise_slug: "pin", status: "approved", fen: null, position_json: {},
        answer_json: {}, hint_json: {}, prompt_fa: "", explanation: "",
        initial_rating: 1200, is_published: false, is_archived: false,
        published_at: null, created_at: "", source: "manual", source_reference: null,
        generator_run_id: null, difficulty: null, target_rating: null, retired_at: null,
      },
    ]);
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );
    // Server-side library: rows link into the detail workspace where
    // lifecycle actions live; filters stay visible for narrowing.
    await waitFor(() => expect(screen.getAllByText("باز کردن").length).toBe(3));
    expect(screen.getByText("همه وضعیت‌ها")).toBeTruthy();
    expect(screen.getByText("همه دشواری‌ها")).toBeTruthy();
    expect(screen.getByText("همه منابع")).toBeTruthy();
    // Each status word appears once in the filter <select> and once
    // per matching row badge.
     expect(screen.getAllByText("پیش‌نویس").length).toBeGreaterThanOrEqual(1);
     expect(screen.getAllByText("اعتبارسنجی‌شده").length).toBeGreaterThanOrEqual(1);
     expect(screen.getAllByText("تأییدشده").length).toBeGreaterThanOrEqual(1);
  });

  it("reveals bulk actions after selecting rows", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.puzzles.mockResolvedValue([
      {
        id: 1, exercise_slug: "pin", status: "draft", fen: null, position_json: {},
        answer_json: {}, hint_json: {}, prompt_fa: "", explanation: "",
        initial_rating: 1200, is_published: false, is_archived: false,
        published_at: null, created_at: "", source: "manual", source_reference: null,
        generator_run_id: null, difficulty: null, target_rating: null, retired_at: null,
      },
    ]);
    mockedAdmin.bulkPuzzles.mockResolvedValue({ action: "validate", succeeded: [1], failed: [] });
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("باز کردن")).toBeTruthy());
    expect(screen.queryByText("اعتبارسنجی گروهی")).toBeNull();
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByText("اعتبارسنجی گروهی")).toBeTruthy();
    await user.click(screen.getByText("اعتبارسنجی گروهی"));
    await waitFor(() => expect(mockedAdmin.bulkPuzzles).toHaveBeenCalledWith({
      puzzle_ids: [1],
      action: "validate",
      reason: "",
    }));
  });
});

describe("admin generators page", () => {
  it("shows the run form and the run history", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.exercises.mockResolvedValue([]);
    mockedAdmin.generators.mockResolvedValue([
      { code: "captures-v1", exercise_slug: "captures", version: "1.0.0", description: "", config_schema: {}, status: "active" },
    ]);
    mockedAdmin.generatorRuns.mockResolvedValue([
      {
        id: 4, generator_code: "captures-v1", generator_version: "1.0.0",
        exercise_slug: "captures", status: "completed", requested_count: 2,
        generated_count: 2, validated_count: 2, accepted_count: 2, rejected_count: 0,
        seed: 7, target_rating: null, difficulty: null, config: {},
        result: { accepted_puzzle_ids: [10, 11], rejected: [] }, error: "",
        requested_by_user_id: 1, created_at: "", updated_at: "", completed_at: "",
      },
    ]);
    render(
      <MemoryRouter initialEntries={["/admin/generators"]}>
        <AdminGeneratorsPage />
      </MemoryRouter>,
    );
     await waitFor(() => expect(screen.getByText("تولید معمای تازه")).toBeTruthy());
     await waitFor(() => expect(screen.getByText("اجراهای مولد")).toBeTruthy());
     await waitFor(() => expect(screen.getByText("تأییدشده")).toBeTruthy());
  });

  it("marks exercises with and without a safe generator", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.exercises.mockResolvedValue([
      { slug: "captures", title_fa: "گرفتن", title_en: "", description: "", is_active: true, sort_order: 1, puzzle_count: 0, published_count: 0, needs_review_count: 0, success_rate: null, low_supply: true },
      { slug: "pin", title_fa: "آچمز", title_en: "", description: "", is_active: true, sort_order: 2, puzzle_count: 0, published_count: 0, needs_review_count: 0, success_rate: null, low_supply: true },
    ]);
    mockedAdmin.generators.mockResolvedValue([
      { code: "captures-v1", exercise_slug: "captures", version: "1.0.0", description: "", config_schema: {}, status: "active" },
    ]);
    mockedAdmin.generatorRuns.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/generators"]}>
        <AdminGeneratorsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("تمرین‌های دارای مولد")).toBeTruthy());
    expect(screen.getByText("تمرین‌های بدون مولد")).toBeTruthy();
     expect(screen.getAllByText(/captures-v1/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("آچمز")).toBeTruthy();
  });

  it("shows the empty state when no runs exist", async () => {
    mockedUseAuth.mockReturnValue(base({ user: ADMIN }));
    mockedAdmin.exercises.mockResolvedValue([]);
    mockedAdmin.generators.mockResolvedValue([]);
    mockedAdmin.generatorRuns.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/generators"]}>
        <AdminGeneratorsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("موردی نیست.").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("اجراهای مولد")).toBeTruthy();
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

  it("follows the active role, not the assigned set", () => {
    // Assigned ADMIN but PLAYER-active: no admin tab, guard blocks.
    const playerActive = { ...ADMIN, active_role: "PLAYER" };
    mockedUseAuth.mockReturnValue(base({ user: playerActive }));
    const { unmount } = render(
      <MemoryRouter initialEntries={["/"]}>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.queryByText("مدیریت")).toBeNull();
    unmount();

    mockedUseAuth.mockReturnValue(base({ user: playerActive }));
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
});
