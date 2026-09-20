import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi, adminBillingApi } from "../api/client";
import { AdminInsightsPage } from "./AdminInsightsPage";
import { AdminReviewQueuePage } from "./AdminReviewQueuePage";
import { AdminSalesPage } from "./AdminSalesPage";
import { AdminSystemPage } from "./AdminSystemPage";
import { AdminAuditPage } from "./AdminAuditPage";

vi.mock("../api/client", () => ({
  adminApi: {
    dashboard: vi.fn(),
    dashboardExtended: vi.fn(),
    userProfile: vi.fn(),
    exercises: vi.fn(),
    exercise: vi.fn(),
    exerciseAnalyticsDetail: vi.fn(),
    reviewQueue: vi.fn(),
    publishPuzzle: vi.fn(),
    quarantinePuzzle: vi.fn(),
    rejectPuzzle: vi.fn(),
    restorePuzzle: vi.fn(),
    salesOverview: vi.fn(),
    insights: vi.fn(),
    systemHealth: vi.fn(),
    audit: vi.fn(),
  },
  adminBillingApi: {
    report: vi.fn(),
    plans: vi.fn(),
    createPlan: vi.fn(),
    createPrice: vi.fn(),
    setPlanActive: vi.fn(),
    setPriceActive: vi.fn(),
    coupons: vi.fn(),
    createCoupon: vi.fn(),
    setCouponActive: vi.fn(),
    campaigns: vi.fn(),
    createCampaign: vi.fn(),
    setCampaignActive: vi.fn(),
    subscriptions: vi.fn(),
    payments: vi.fn(),
    redemptions: vi.fn(),
  },
  apiDetail: () => "",
}));

const mockedAdmin = vi.mocked(adminApi, true);
const mockedBilling = vi.mocked(adminBillingApi, true);

beforeEach(() => {
  vi.resetAllMocks();
});

describe("admin ops pages", () => {
  it("review queue shows empty state in Persian", async () => {
    mockedAdmin.reviewQueue.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AdminReviewQueuePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("صف بازبینی").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("موردی نیست.")).toBeTruthy();
  });

  it("review queue lists items with severity and actions", async () => {
    mockedAdmin.reviewQueue.mockResolvedValue([
      {
        id: 9, exercise_slug: "pin", status: "quarantined", source: "generated",
        difficulty: 2, initial_rating: 1200, created_at: "", attempts: 8,
        failure_rate: 0.875, severity: "high", reasons: ["quarantined", "high_failure_rate"],
      },
    ]);
    render(
      <MemoryRouter>
        <AdminReviewQueuePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("قرنطینه")).toBeTruthy());
    expect(screen.getByText("بازیابی")).toBeTruthy();
  });

  it("sales page renders revenue and campaign rows", async () => {
    mockedAdmin.salesOverview.mockResolvedValue({
      subscriptions_by_status: [{ status: "active", count: 3 }],
      payments_by_status: [{ status: "verified", count: 2 }],
      revenue_minor: 500000,
      revenue_currency: "IRR",
      redemptions_total: 4,
    });
    mockedBilling.report.mockResolvedValue([
      { slug: "abad", source: "s", medium: "", registrations: 10, redemptions: 4, trials: 2, paid: 1 },
    ]);
    render(
      <MemoryRouter>
        <AdminSalesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("فروش").length).toBeGreaterThanOrEqual(1));
  });

  it("sales plans tab lists price history and toggles", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    mockedAdmin.salesOverview.mockResolvedValue({
      subscriptions_by_status: [],
      payments_by_status: [],
      revenue_minor: 0,
      revenue_currency: "IRR",
      redemptions_total: 0,
    });
    mockedBilling.report.mockResolvedValue([]);
    mockedBilling.plans.mockResolvedValue([
      {
        code: "club", name_fa: "باشگاهی", description_fa: "", billing_interval: "monthly",
        is_active: true, sort_order: 1,
        prices: [
          { id: 3, version: 2, amount_minor: 100000, currency: "IRR", billing_interval: "monthly", is_active: true, effective_from: null },
        ],
      },
    ]);
    mockedBilling.setPriceActive.mockResolvedValue({} as never);
    window.confirm = vi.fn(() => true);
    render(
      <MemoryRouter>
        <AdminSalesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("فروش").length).toBeGreaterThanOrEqual(1));
    await user.click(screen.getByRole("button", { name: "طرح‌ها" }));
    await waitFor(() => expect(screen.getByText("باشگاهی")).toBeTruthy());
    expect(screen.getByText("تاریخچه قیمت‌ها")).toBeTruthy();
    await user.click(screen.getAllByRole("button", { name: "غیرفعال کردن" })[1]);
    await waitFor(() => expect(mockedBilling.setPriceActive).toHaveBeenCalledWith(3, false));
  });

  it("sales coupons tab lists coupons with usage and limits", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    mockedAdmin.salesOverview.mockResolvedValue({
      subscriptions_by_status: [],
      payments_by_status: [],
      revenue_minor: 0,
      revenue_currency: "IRR",
      redemptions_total: 0,
    });
    mockedBilling.report.mockResolvedValue([]);
    mockedBilling.coupons.mockResolvedValue([
      {
        id: 5, code: "SHOP10", campaign_slug: "camp", discount_type: "percent", discount_value: 10,
        trial_days: 0, is_active: true, valid_from: null, valid_until: null, max_redemptions: 100,
        max_per_user: 1, total_redemptions: 4, applicable_plan_codes: ["premium"],
      },
    ]);
    mockedBilling.redemptions.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AdminSalesPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("فروش").length).toBeGreaterThanOrEqual(1));
    await user.click(screen.getByRole("button", { name: "کوپن‌ها" }));
    await waitFor(() => expect(screen.getByText("SHOP10")).toBeTruthy());
    await user.click(screen.getByText("SHOP10"));
    await waitFor(() => expect(mockedBilling.redemptions).toHaveBeenCalledWith(
      expect.objectContaining({ coupon_code: "SHOP10" }),
    ));
  });

  it("insights page shows empty state", async () => {
    mockedAdmin.insights.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AdminInsightsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("بینش محصول").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("موردی نیست.")).toBeTruthy();
  });

  it("system page renders health snapshot", async () => {
    mockedAdmin.systemHealth.mockResolvedValue({
      ok: true,
      database: { reachable: true },
      schema_status: { expected: 15, stored: 15, ok: true },
      puzzles: { total: 10, published: 6 },
    });
    render(
      <MemoryRouter>
        <AdminSystemPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("سلامت سامانه").length).toBeGreaterThanOrEqual(1));
  });

  it("audit page shows empty state", async () => {
    mockedAdmin.audit.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AdminAuditPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByText("گزارش حسابرسی").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("هنوز رویداد مدیریتی ثبت نشده است.")).toBeTruthy();
  });

  it("exercise detail renders supply, difficulty, mistakes, and recommendations", async () => {
    const { AdminExerciseDetailPage } = await import("./AdminExerciseDetailPage");
    const { Route, Routes } = await import("react-router-dom");
    mockedAdmin.exercise.mockResolvedValue({
      slug: "pin", title_fa: "آچمز", title_en: "Pin", description: "", is_active: true,
      sort_order: 1, puzzle_count: 10, published_count: 6, needs_review_count: 2,
      success_rate: 0.6, low_supply: false, attempts_count: 50,
    });
    mockedAdmin.exerciseAnalyticsDetail.mockResolvedValue({
      exercise: "pin", is_active: true, attempts: 50, unique_players: 8, correct: 30,
      partial: 5, wrong: 15, accuracy: 0.6, avg_response_ms: null, active_days: 6,
      puzzles_total: 10, puzzles_published: 6, rating_events_in_period: 4,
      rating_delta_sum_in_period: 3.5, current_ratings: 5, current_rating_avg: 1210,
      period: "30d", start: null, end: "", terminal: 0, total_practice_ms: 0,
      by_mode: [], daily: [],
      supply_by_status: [{ status: "published", count: 6 }, { status: "validated", count: 2 }],
      difficulty_distribution: [{ difficulty: 2, count: 6 }],
      mistake_distribution: [{ mistake: "wrong_target", count: 9 }],
      recommendation_outcomes: [{ status: "completed", count: 3 }],
    });
    render(
      <MemoryRouter initialEntries={["/admin/exercises/pin"]}>
        <Routes>
          <Route path="/admin/exercises/:slug" element={<AdminExerciseDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("جزئیات تمرین")).toBeTruthy());
    expect(screen.getByText("موجودی معما بر اساس وضعیت")).toBeTruthy();
    expect(screen.getByText("توزیع دشواری")).toBeTruthy();
    expect(screen.getByText("توزیع خطاها")).toBeTruthy();
    expect(screen.getByText("سرانجام پیشنهادها")).toBeTruthy();
    expect(screen.getByText("wrong_target")).toBeTruthy();
  });

  it("user detail renders 360 tabs with timeline", async () => {
    const { AdminUserDetailPage } = await import("./AdminUserDetailPage");
    const { Route, Routes } = await import("react-router-dom");
    const user = (await import("@testing-library/user-event")).default.setup();
    mockedAdmin.userProfile.mockResolvedValue({
      overview: {
        id: 7, username: "kid", display_name: "kid", roles: ["PLAYER"], is_active: true,
        created_at: "2026-09-01T00:00:00", last_active_at: "2026-09-10T00:00:00", attempts_total: 12,
      },
      learning: {
        attempts_by_exercise: [{ exercise_slug: "pin", attempts: 12, correct: 8 }],
        skills: [{ skill: "pin", level: "emerging", confidence: "medium", evidence_count: 4 }],
        overall_level: "emerging",
        overall_confidence: "medium",
        mastery: [{ skill: "pin", status: "developing", confidence: "medium", attempts: 6 }],
        xp: { total: 120, level: 2 },
        streak: { current: 3, longest: 5 },
      },
      commercial: {
        current_subscription: {
          plan_code: "free", status: "active", source: "free_beta", trial_ends_at: null,
          current_period_end: null, coupon_code: null,
        },
        subscriptions: [],
        attribution: null,
        redemptions: [],
        payments: [],
      },
      timeline: [
        { kind: "first_attempt", at: "2026-09-02T00:00:00", detail: "", durable: true },
        { kind: "registered", at: "2026-09-01T00:00:00", detail: "kid", durable: true },
      ],
    });
    render(
      <MemoryRouter initialEntries={["/admin/users/7"]}>
        <Routes>
          <Route path="/admin/users/:id" element={<AdminUserDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("جزئیات کاربر")).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "یادگیری" }));
    await waitFor(() => expect(screen.getByText("مهارت‌های دیده‌شده")).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "خط زمانی" }));
    await waitFor(() => expect(screen.getByText("نخستین تلاش")).toBeTruthy());
    expect(screen.getByText("ثبت‌نام")).toBeTruthy();
  });

  it("dashboard renders extended revenue, attribution, and exercise success", async () => {
    const { AdminDashboardPage } = await import("./AdminDashboardPage");
    mockedAdmin.dashboard.mockResolvedValue({
      users_total: 5,
      users_active: 4,
      users_suspended: 1,
      exercises_total: 2,
      exercises_active: 2,
      puzzles_total: 10,
      puzzles_published: 6,
      puzzles_archived: 0,
      attempts_total: 40,
      attempts_last_24h: 5,
      recent_registrations: [],
      recent_audit: [],
    });
    mockedAdmin.dashboardExtended.mockResolvedValue({
      users_total: 5,
      registrations: { today: 1, week: 3, month: 5 },
      active: { today: 2, week: 4 },
      attempts: { today: 5, week: 30, prev_week: 20 },
      sales: {
        subscriptions_by_status: [],
        payments_by_status: [],
        revenue_minor: 200000,
        revenue_currency: "IRR",
        redemptions_total: 2,
      },
      alerts: 0,
      series: [
        { day: "2026-09-01", registrations: 1, attempts: 5, revenue_minor: 200000, redemptions: 1, new_subscriptions: 1 },
      ],
      attribution: [
        { slug: "abad", source: "s", medium: "", registrations: 5, redemptions: 2, trials: 1, paid: 0 },
      ],
      exercise_success: [{ exercise_slug: "pin", attempts: 40, success_rate: 0.625 }],
    });
    mockedAdmin.insights.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("روند درآمد")).toBeTruthy());
    expect(screen.getByText("جذب بر اساس کمپین")).toBeTruthy();
    expect(screen.getByText("موفقیت تمرین‌ها")).toBeTruthy();
    expect(screen.getByText("abad")).toBeTruthy();
  });

  it("shows loading then error with retry", async () => {
    mockedAdmin.insights.mockRejectedValue(new Error("boom"));
    render(
      <MemoryRouter>
        <AdminInsightsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
  });
});
