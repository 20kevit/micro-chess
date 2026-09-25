import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import { AdminSystemPage } from "./AdminSystemPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      systemHealth: vi.fn(),
      providerHealth: vi.fn(),
      journeyOverview: vi.fn(),
    },
  };
});

const mocked = vi.mocked(adminApi, true);

beforeEach(() => {
  vi.resetAllMocks();
  mocked.systemHealth.mockResolvedValue({
    ok: true,
    database: { reachable: true },
    schema_status: { expected: 16, stored: 16, ok: true },
    puzzles: { total: 20, published: 12 },
    providers: {
      vapid: { configured: true, available: true },
      telegram: { configured: true, available: true },
      bale: { configured: false, available: false },
      channels: {},
      billing: { provider: "none", available: false },
    },
    channels: {},
  });
  mocked.providerHealth.mockResolvedValue({
    vapid: { configured: true, available: true },
    telegram: { configured: true, available: true },
    bale: { configured: false, available: false },
    channels: { web_push: { available: true, subscriptions: 3 } },
    billing: { provider: "none", available: false },
  });
  mocked.journeyOverview.mockResolvedValue({
    onboarding_completed: 4,
    placement_completed: 3,
    phones_verified: 2,
    telegram_verified: 1,
    bale_verified: 0,
    free_users: 8,
    premium_users: 2,
    premium_activations: 2,
    coupon_redemptions: 1,
    users_at_daily_limit: 1,
    quest_days: 5,
    quests_completed: 12,
    quests_total: 15,
    quest_completion_rate: 0.8,
    push_subscriptions: 3,
    telegram_links: 1,
    bale_links: 0,
    notification_delivery_failures: 0,
    events: { secret_token: 1 },
  });
});

describe("P13 system health", () => {
  it("shows provider and journey signals without configuration secrets", async () => {
    render(<MemoryRouter><AdminSystemPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("سلامت سامانه")).toBeTruthy());
    expect(screen.getAllByText("تلگرام").length).toBeGreaterThan(0);
    expect(screen.getByText("فعال‌سازی حساب ویژه")).toBeTruthy();
    expect(screen.getByText("۸۰٪")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("must-not-render");
  });
});
