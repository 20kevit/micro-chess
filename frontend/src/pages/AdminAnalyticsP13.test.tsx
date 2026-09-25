import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminPlatformAnalytics } from "../api/types";
import { AdminAnalyticsPage } from "./AdminAnalyticsPage";
import { AdminInsightsPage } from "./AdminInsightsPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      platformAnalytics: vi.fn(),
      exerciseAnalytics: vi.fn(),
      puzzleAnalytics: vi.fn(),
      retention: vi.fn(),
      learning: vi.fn(),
      recommendationStats: vi.fn(),
      insights: vi.fn(),
    },
  };
});

const mocked = vi.mocked(adminApi, true);

function platform(): AdminPlatformAnalytics {
  return {
    period: "7d",
    start: "2026-09-01T00:00:00",
    end: "2026-09-20T00:00:00",
    users_total: 0,
    new_registrations: 0,
    active_users: 0,
    totals: { attempts: 0, correct: 0, partial: 0, wrong: 0, terminal: 0, accuracy: 0, avg_response_ms: null, total_practice_ms: 0, active_days: 0 },
    by_mode: [],
    exercise_usage: [],
    daily: [],
    ratings: { events_in_period: 0, delta_sum_in_period: 0, current_rows: 0 },
    xp: { earned_in_period: 0, events_in_period: 0 },
    comparison: null,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.platformAnalytics.mockResolvedValue(platform());
  mocked.exerciseAnalytics.mockResolvedValue([]);
  mocked.puzzleAnalytics.mockResolvedValue([]);
  mocked.retention.mockResolvedValue({ cohorts: [], offsets: [1, 7, 14, 30] });
  mocked.learning.mockResolvedValue({ window_days: 30, exercise_usage: [], mistake_distribution: [], direction_distribution: [], top_skills: [] });
  mocked.recommendationStats.mockResolvedValue({ window_days: 30, total: 0, by_status: [], by_reason: [], by_exercise: [] });
  mocked.insights.mockResolvedValue([]);
});

describe("P13 admin analytics", () => {
  it("shows Persian empty states without technical activity labels", async () => {
    render(<MemoryRouter><AdminAnalyticsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("تحلیل‌ها")).toBeTruthy());
    expect(screen.getAllByText("در این بازه تمرینی ثبت نشده است.").length).toBeGreaterThan(0);
    expect(document.body.textContent ?? "").not.toContain("wrong_target");
  });

  it("loads a custom date period", async () => {
    const actor = userEvent.setup();
    render(<MemoryRouter><AdminAnalyticsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText("تحلیل‌ها")).toBeTruthy());
    await actor.selectOptions(screen.getByLabelText("تحلیل‌ها"), "custom");
    fireEvent.change(screen.getByLabelText("از تاریخ"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("تا تاریخ"), { target: { value: "2026-09-20" } });
    await waitFor(() => expect(mocked.platformAnalytics).toHaveBeenCalledWith({ period: "custom", date_from: "2026-09-01", date_to: "2026-09-20" }));
  });

  it("uses Persian empty copy for insights", async () => {
    render(<MemoryRouter><AdminInsightsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("بینش محصول")).toBeTruthy());
    expect(screen.getByText("موردی نیست.")).toBeTruthy();
  });
});
