import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminUser, UserProfileFull } from "../api/types";
import { AdminUserDetailPage } from "./AdminUserDetailPage";
import { AdminUsersPage } from "./AdminUsersPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      usersPage: vi.fn(),
      users: vi.fn(),
      user: vi.fn(),
      userProfile: vi.fn(),
      suspendUser: vi.fn(),
      reactivateUser: vi.fn(),
      assignRole: vi.fn(),
      revokeRole: vi.fn(),
    },
  };
});

const mocked = vi.mocked(adminApi, true);

const user: AdminUser = {
  id: 7,
  username: "kid",
  display_name: "بازیکن",
  roles: ["PLAYER"],
  is_active: true,
  created_at: "2026-09-01T00:00:00",
  current_plan_code: "free",
  current_plan_status: "active",
  verification_channel: null,
  phone_verified: false,
  last_active_at: "2026-09-10T00:00:00",
  attempts_count: 12,
  coupon_redemption_count: 2,
};

const profile: UserProfileFull = {
  overview: {
    id: 7,
    username: "kid",
    display_name: "بازیکن",
    roles: ["PLAYER"],
    is_active: true,
    created_at: "2026-09-01T00:00:00",
    last_active_at: "2026-09-10T00:00:00",
    attempts_total: 12,
    phone_verified: true,
    verification_channel: "telegram",
    phone_masked: "+98•••1234",
    verification: { verified: true, phone_masked: "+98•••1234", channel: "telegram", available_channels: ["telegram"] },
  },
  verification: { verified: true, phone_masked: "+98•••1234", channel: "telegram", available_channels: ["telegram"] },
  learning: {
    attempts_by_exercise: [],
    skills: [],
    overall_level: "emerging",
    overall_confidence: "medium",
    mastery: [],
    xp: { total: 20, level: 1 },
    streak: { current: 2, longest: 3 },
  },
  commercial: {
    current_subscription: null,
    subscriptions: [],
    attribution: null,
    redemptions: [],
    payments: [],
  },
  timeline: [],
};

beforeEach(() => {
  vi.resetAllMocks();
  mocked.usersPage.mockResolvedValue({ items: [user], total: 1 });
  mocked.users.mockResolvedValue([user]);
  mocked.userProfile.mockResolvedValue(profile);
  mocked.suspendUser.mockResolvedValue({ ...user, is_active: false });
  window.confirm = vi.fn(() => true);
});

describe("P13 admin users", () => {
  it("uses a paginated table and canonical detail links", async () => {
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("kid")).toBeTruthy());
    expect(screen.getByText("استفاده از کوپن")).toBeTruthy();
    expect(screen.getByRole("link", { name: "kid" }).getAttribute("href")).toBe("/admin/users/7");
    expect(mocked.usersPage).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20, sort: "created_at", order: "desc" }));
    expect(mocked.user).not.toHaveBeenCalled();
  });

  it("passes role and order filters to the server", async () => {
    const actor = userEvent.setup();
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText("همه نقش‌ها")).toBeTruthy());
    await actor.selectOptions(screen.getByLabelText("همه نقش‌ها"), "COACH");
    await actor.selectOptions(screen.getByLabelText("نزولی"), "asc");
    await waitFor(() => expect(mocked.usersPage).toHaveBeenCalledWith(expect.objectContaining({ role: "COACH", order: "asc", page: 1 })));
  });

  it("keeps masked verification and account actions on the canonical detail page", async () => {
    const actor = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/admin/users/7"]}>
        <Routes><Route path="/admin/users/:id" element={<AdminUserDetailPage />} /></Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("جزئیات کاربر")).toBeTruthy());
    expect(screen.getByText(/\+98•••1234/)).toBeTruthy();
    expect(screen.getByText(/تأیید با تلگرام/)).toBeTruthy();
    await actor.click(screen.getByRole("button", { name: "تعلیق" }));
    await waitFor(() => expect(mocked.suspendUser).toHaveBeenCalledWith(7));
  });
});
