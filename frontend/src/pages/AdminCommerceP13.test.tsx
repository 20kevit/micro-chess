import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi, adminBillingApi } from "../api/client";
import { AdminSalesPage } from "./AdminSalesPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      salesOverview: vi.fn(),
    },
    adminBillingApi: {
      report: vi.fn(),
      plans: vi.fn(),
      coupons: vi.fn(),
      campaigns: vi.fn(),
      createCoupon: vi.fn(),
      setCouponActive: vi.fn(),
      redemptionsPage: vi.fn(),
      redemptions: vi.fn(),
      subscriptionsPage: vi.fn(),
      subscriptions: vi.fn(),
      paymentsPage: vi.fn(),
      payments: vi.fn(),
    },
  };
});

const mockedAdmin = vi.mocked(adminApi, true);
const mockedBilling = vi.mocked(adminBillingApi, true);

beforeEach(() => {
  vi.resetAllMocks();
  mockedAdmin.salesOverview.mockResolvedValue({
    subscriptions_by_status: [],
    payments_by_status: [],
    revenue_minor: 0,
    revenue_currency: "IRR",
    redemptions_total: 0,
  });
  mockedBilling.report.mockResolvedValue([]);
  mockedBilling.plans.mockResolvedValue([{
    code: "premium",
    name_fa: "حرفه‌ای",
    description_fa: "",
    billing_interval: "monthly",
    is_active: true,
    sort_order: 1,
    prices: [],
  }]);
  mockedBilling.campaigns.mockResolvedValue([{
    slug: "school",
    name_fa: "مدرسه",
    source: "referral",
    medium: "message",
    content: "",
    is_active: true,
  }]);
  mockedBilling.coupons.mockResolvedValue([]);
  mockedBilling.subscriptionsPage.mockResolvedValue({ items: [], total: 0 });
  mockedBilling.paymentsPage.mockResolvedValue({ items: [], total: 0 });
  mockedBilling.redemptionsPage.mockResolvedValue({ items: [], total: 0 });
  mockedBilling.createCoupon.mockResolvedValue({
    id: 1,
    code: "TEST10",
    campaign_slug: null,
    description: "",
    discount_type: "percent",
    discount_value: 10,
    trial_days: 0,
    currency: "IRR",
    is_active: true,
    valid_from: null,
    valid_until: null,
    max_redemptions: null,
    max_per_user: 1,
    first_time_only: false,
    min_amount_minor: 0,
    total_redemptions: 0,
    applicable_plan_codes: [],
  });
});

describe("P13 commerce and coupons", () => {
  it("opens the query-param coupon tab with Persian types and backend plan choices", async () => {
    render(<MemoryRouter initialEntries={["/admin/sales?tab=coupons"]}><AdminSalesPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("option", { name: /دسترسی رایگان/ })).toBeTruthy());
    expect(screen.getByRole("option", { name: "حرفه‌ای (premium)" })).toBeTruthy();
    expect(screen.getAllByText("ساخت کوپن").length).toBeGreaterThan(0);
    expect(mockedBilling.plans).toHaveBeenCalled();
  });

  it("submits a coupon without comma-separated plan identifiers", async () => {
    const actor = userEvent.setup();
    render(<MemoryRouter initialEntries={["/admin/sales?tab=coupons"]}><AdminSalesPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getAllByText("ساخت کوپن").length).toBeGreaterThan(0));
    await actor.type(screen.getByLabelText("کد کوپن"), "TEST10");
    await actor.click(screen.getByRole("button", { name: "ساخت کوپن" }));
    await waitFor(() => expect(mockedBilling.createCoupon).toHaveBeenCalledWith(expect.objectContaining({
      code: "TEST10",
      discount_type: "percent",
      applicable_plan_codes: [],
    })));
  });

  it("keeps payment records typed, linked, and honestly read-only", async () => {
    mockedBilling.paymentsPage.mockResolvedValue({
      items: [{
        id: 3,
        user_id: 12,
        subscription_id: 8,
        plan_code: "premium",
        price_amount_minor: 100000,
        discount_minor: 10000,
        final_amount_minor: 90000,
        currency: "IRR",
        coupon_code: "TEST10",
        provider: "none",
        provider_ref: null,
        status: "verified",
        failure_reason: "",
        created_at: "2026-09-20T00:00:00",
      }],
      total: 1,
    });
    render(<MemoryRouter initialEntries={["/admin/sales?tab=payments"]}><AdminSalesPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("TEST10")).toBeTruthy());
    expect(screen.getByRole("link", { name: /کاربر ۱۲/ }).getAttribute("href")).toBe("/admin/users/12");
    expect(screen.getByText("هیچ درگاه پرداخت واقعی متصل نیست. رکوردهای موجود نمایش داده می‌شوند و تراکنش یا درآمدی ساخته نمی‌شود.")).toBeTruthy();
    expect(mockedBilling.paymentsPage).toHaveBeenCalledWith({ status: undefined, page: 1, page_size: 20 });
  });
});
