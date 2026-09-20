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
