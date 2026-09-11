import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type {
  AdminExerciseAnalytics,
  AdminPlatformAnalytics,
  AdminPuzzleAnalytics,
} from "../api/types";
import { AdminAnalyticsPage } from "./AdminAnalyticsPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    adminApi: {
      platformAnalytics: vi.fn(),
      exerciseAnalytics: vi.fn(),
      puzzleAnalytics: vi.fn(),
    },
  };
});

const mockedAdmin = vi.mocked(adminApi, true);

function platform(): AdminPlatformAnalytics {
  return {
    period: "7d",
    start: "2026-09-04T00:00:00",
    end: "2026-09-11T00:00:00",
    users_total: 5,
    new_registrations: 2,
    active_users: 3,
    totals: {
      attempts: 10,
      correct: 7,
      partial: 1,
      wrong: 2,
      terminal: 0,
      accuracy: 0.7,
      avg_response_ms: null,
      total_practice_ms: 0,
      active_days: 4,
    },
    by_mode: [],
    exercise_usage: [],
    daily: [],
    ratings: { events_in_period: 4, delta_sum_in_period: 5.5, current_rows: 2 },
    xp: { earned_in_period: 80, events_in_period: 10 },
    comparison: { attempts: 3, accuracy: 0.1, active_users: 1, xp_earned: 20 },
  };
}

function exercises(): AdminExerciseAnalytics[] {
  return [
    {
      exercise: "piece-recognition",
      is_active: true,
      attempts: 10,
      unique_players: 3,
      correct: 7,
      partial: 1,
      wrong: 2,
      accuracy: 0.7,
      avg_response_ms: null,
      active_days: 4,
      puzzles_total: 12,
      puzzles_published: 10,
      rating_events_in_period: 4,
      rating_delta_sum_in_period: 5.5,
      current_ratings: 2,
      current_rating_avg: 1210.5,
    },
  ];
}

function puzzles(): AdminPuzzleAnalytics[] {
  return [
    {
      puzzle_id: 42,
      exercise_slug: "piece-recognition",
      status: "published",
      difficulty: 2,
      initial_rating: 1200,
      attempts: 8,
      correct: 2,
      accuracy: 0.25,
      failure_rate: 0.75,
      unique_players: 3,
      repeated_failures: 1,
      observed_difficulty: "hard",
      avg_response_ms: null,
    },
  ];
}

beforeEach(() => {
  vi.resetAllMocks();
});

function renderPage() {
  render(
    <MemoryRouter>
      <AdminAnalyticsPage />
    </MemoryRouter>,
  );
}

describe("admin analytics page", () => {
  it("renders platform cards, exercise usage, and puzzle performance", async () => {
    mockedAdmin.platformAnalytics.mockResolvedValue(platform());
    mockedAdmin.exerciseAnalytics.mockResolvedValue(exercises());
    mockedAdmin.puzzleAnalytics.mockResolvedValue(puzzles());
    renderPage();
    await waitFor(() => expect(screen.getByText("تحلیل‌ها")).toBeTruthy());
    expect(screen.getByText("کاربران فعال")).toBeTruthy();
    expect(screen.getByText("استفاده تمرین‌ها")).toBeTruthy();
    expect(screen.getByText("عملکرد معماها")).toBeTruthy();
    // Observed difficulty label, never raw codes or answers.
    expect(screen.getByText("سخت")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("answer_json");
  });

  it("renders empty states when there is no activity", async () => {
    mockedAdmin.platformAnalytics.mockResolvedValue({ ...platform(), totals: { ...platform().totals, attempts: 0 } });
    mockedAdmin.exerciseAnalytics.mockResolvedValue([]);
    mockedAdmin.puzzleAnalytics.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("تحلیل‌ها")).toBeTruthy());
    expect(screen.getAllByText("موردی نیست.").length).toBeGreaterThan(0);
  });

  it("reloads every source when the period changes", async () => {
    const user = userEvent.setup();
    mockedAdmin.platformAnalytics.mockResolvedValue(platform());
    mockedAdmin.exerciseAnalytics.mockResolvedValue(exercises());
    mockedAdmin.puzzleAnalytics.mockResolvedValue(puzzles());
    renderPage();
    await waitFor(() => expect(screen.getByText("تحلیل‌ها")).toBeTruthy());
    const select = screen.getByLabelText("تحلیل‌ها") as HTMLSelectElement;
    await user.selectOptions(select, "all");
    await waitFor(() =>
      expect(mockedAdmin.platformAnalytics).toHaveBeenCalledWith({ period: "all" }),
    );
    expect(mockedAdmin.exerciseAnalytics).toHaveBeenCalledWith({ period: "all" });
    expect(mockedAdmin.puzzleAnalytics).toHaveBeenCalledWith({ period: "all", page_size: 20 });
  });

  it("shows an error with retry", async () => {
    const user = userEvent.setup();
    mockedAdmin.platformAnalytics.mockRejectedValueOnce(new Error("boom"));
    mockedAdmin.exerciseAnalytics.mockResolvedValue([]);
    mockedAdmin.puzzleAnalytics.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    mockedAdmin.platformAnalytics.mockResolvedValue(platform());
    await user.click(screen.getByText("تلاش دوباره"));
    await waitFor(() => expect(screen.getByText("کاربران فعال")).toBeTruthy());
  });
});
