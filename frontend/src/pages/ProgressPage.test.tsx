import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProgressPage } from "./ProgressPage";
import type { HistoryAttempt, ProgressSummary } from "../api/types";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    progress: vi.fn(),
    trainingAttempts: vi.fn(),
    getRatings: vi.fn(),
    getGamification: vi.fn(),
    getAchievements: vi.fn(),
    getXpHistory: vi.fn(),
    getAnalytics: vi.fn(),
    getAnalyticsComparison: vi.fn(),
    adaptiveOverview: vi.fn(),
    adaptiveNext: vi.fn(),
    adaptiveOutcome: vi.fn(),
    recommendation: vi.fn(),
  },
  apiStatus: () => null,
}));

const mockedApi = vi.mocked(api, true);

const EMPTY: ProgressSummary = { attempts: 0, correct: 0, accuracy: 0, exercises: [] };

function attempt(id: number): HistoryAttempt {
  return {
    id,
    puzzle_id: 10 + id,
    exercise_slug: "piece-recognition",
    mode: "practice",
    result: id === 1 ? "correct" : "wrong",
    score: 1,
    duration_ms: null,
    hints_used: [],
    rating_before: null,
    rating_delta: null,
    rating_after: null,
    created_at: "2026-09-01T10:00:00",
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getRatings.mockResolvedValue({ items: [] });
  mockedApi.adaptiveOverview.mockResolvedValue({ exercises: [], recommended_exercise: null, reason: null });
  mockedApi.recommendation.mockResolvedValue(null);
  mockedApi.getGamification.mockResolvedValue({
    xp: { total: 0, level: 1, xp_in_level: 0, xp_for_next: 100 },
    streak: { current: 0, longest: 0 },
    achievements_unlocked: 0,
    total_achievements: 4,
  });
  mockedApi.getAchievements.mockResolvedValue({ items: [] });
  mockedApi.getXpHistory.mockResolvedValue({ items: [] });
  mockedApi.getAnalytics.mockResolvedValue({
    period: "7d",
    start: null,
    end: "2026-09-11T00:00:00",
    exercise: null,
    totals: {
      attempts: 0,
      correct: 0,
      partial: 0,
      wrong: 0,
      terminal: 0,
      accuracy: 0,
      avg_response_ms: null,
      total_practice_ms: 0,
      active_days: 0,
    },
    by_mode: [],
    by_exercise: [],
    daily: [],
    ratings: [],
    xp: { earned_in_period: 0, events_in_period: 0, total: 0, level: 1 },
    streak: { current: 0, longest: 0 },
  });
  mockedApi.getAnalyticsComparison.mockResolvedValue({
    period: "7d",
    exercise: null,
    current: {
      start: "2026-09-04T00:00:00",
      end: "2026-09-11T00:00:00",
      attempts: 0,
      accuracy: 0,
      avg_response_ms: null,
      active_days: 0,
      xp_earned: 0,
      rating_delta: 0,
    },
    previous: {
      start: "2026-08-28T00:00:00",
      end: "2026-09-04T00:00:00",
      attempts: 0,
      accuracy: 0,
      avg_response_ms: null,
      active_days: 0,
      xp_earned: 0,
      rating_delta: 0,
    },
    delta: { attempts: 0, accuracy: 0, active_days: 0, xp_earned: 0, rating_delta: 0 },
  });
});

function renderPage() {
  render(
    <MemoryRouter>
      <ProgressPage />
    </MemoryRouter>,
  );
}

describe("progress page", () => {
  it("renders the empty state for a new player", async () => {
    mockedApi.progress.mockResolvedValue(EMPTY);
    mockedApi.trainingAttempts.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("پیشرفت من")).toBeTruthy());
    expect(screen.getAllByText("هنوز تمرینی ثبت نشده است.").length).toBeGreaterThan(0);
  });

  it("renders totals, per-exercise rows, and history with filters", async () => {
    const user = userEvent.setup();
    mockedApi.progress.mockResolvedValue({
      attempts: 2,
      correct: 1,
      accuracy: 0.5,
      exercises: [
        {
          exercise: "piece-recognition",
          attempts: 2,
          correct: 1,
          accuracy: 0.5,
          last_practiced_at: "2026-09-01T10:00:00",
        },
      ],
    });
    mockedApi.trainingAttempts.mockResolvedValue([attempt(2), attempt(1)]);
    renderPage();
    await waitFor(() => expect(screen.getByText("تاریخچه تمرین‌ها")).toBeTruthy());
    expect(screen.getAllByText("تشخیص مهره").length).toBeGreaterThan(0);
    expect(screen.getByText("درست")).toBeTruthy();
    expect(screen.getByText("اشتباه")).toBeTruthy();

    mockedApi.trainingAttempts.mockResolvedValue([attempt(1)]);
    await user.selectOptions(screen.getByLabelText("نتیجه"), "true");
    await waitFor(() =>
      expect(mockedApi.trainingAttempts).toHaveBeenCalledWith(
        expect.objectContaining({ correct: true, page: 1 }),
      ),
    );
    expect(screen.queryByText("اشتباه")).toBeNull();
  });

  it("shows an error with retry", async () => {
    mockedApi.progress.mockRejectedValue(new Error("down"));
    mockedApi.trainingAttempts.mockRejectedValue(new Error("down"));
    renderPage();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    expect(screen.getByRole("button", { name: "تلاش دوباره" })).toBeTruthy();
  });
});
