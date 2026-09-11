import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { PlayerAnalytics, PlayerComparison } from "../../api/types";
import { AnalyticsSection } from "./AnalyticsSection";

vi.mock("../../api/client", () => ({
  api: {
    getAnalytics: vi.fn(),
    getAnalyticsComparison: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

function overview(attempts: number): PlayerAnalytics {
  return {
    period: "7d",
    start: "2026-09-04T00:00:00",
    end: "2026-09-11T00:00:00",
    exercise: null,
    totals: {
      attempts,
      correct: attempts,
      partial: 0,
      wrong: 0,
      terminal: 0,
      accuracy: attempts === 0 ? 0 : 1,
      avg_response_ms: null,
      total_practice_ms: 0,
      active_days: attempts === 0 ? 0 : 2,
    },
    by_mode: attempts === 0 ? [] : [{ mode: "practice", attempts, correct: attempts, accuracy: 1 }],
    by_exercise:
      attempts === 0
        ? []
        : [
            {
              exercise: "piece-recognition",
              attempts,
              correct: attempts,
              accuracy: 1,
              avg_response_ms: null,
              last_practiced_at: "2026-09-11T00:00:00",
            },
          ],
    daily:
      attempts === 0
        ? []
        : [
            { bucket_start: "2026-09-10", attempts, correct: attempts, accuracy: 1, xp: 20 },
            { bucket_start: "2026-09-11", attempts: 0, correct: 0, accuracy: 0, xp: 0 },
          ],
    ratings: [],
    xp: { earned_in_period: 20, events_in_period: 2, total: 20, level: 1 },
    streak: { current: 2, longest: 2 },
  };
}

function comparison(): PlayerComparison {
  const side = (attempts: number, accuracy: number) => ({
    start: "2026-09-04T00:00:00",
    end: "2026-09-11T00:00:00",
    attempts,
    accuracy,
    avg_response_ms: null,
    active_days: attempts,
    xp_earned: attempts * 10,
    rating_delta: 0,
  });
  return {
    period: "7d",
    exercise: null,
    current: side(2, 1),
    previous: side(1, 0),
    delta: { attempts: 1, accuracy: 1, active_days: 1, xp_earned: 10, rating_delta: 0 },
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("analytics section", () => {
  it("renders summary, trend heading, comparison, and per-exercise rows", async () => {
    mockedApi.getAnalytics.mockResolvedValue(overview(2));
    mockedApi.getAnalyticsComparison.mockResolvedValue(comparison());
    render(<AnalyticsSection />);
    await waitFor(() => expect(screen.getByText("تحلیل تمرین")).toBeTruthy());
    expect(screen.getByText("روند روزانه")).toBeTruthy();
    expect(screen.getByText("مقایسه با دوره قبل")).toBeTruthy();
    expect(screen.getByText("عملکرد هر تمرین")).toBeTruthy();
    // Comparison delta +1 attempt renders with a Persian plus sign.
    expect(mockedApi.getAnalytics).toHaveBeenCalledWith({ period: "7d" });
  });

  it("renders the empty state without comparison for a quiet period", async () => {
    mockedApi.getAnalytics.mockResolvedValue(overview(0));
    mockedApi.getAnalyticsComparison.mockResolvedValue(comparison());
    render(<AnalyticsSection />);
    await waitFor(() => expect(screen.getByText("در این بازه تمرینی ثبت نشده است.")).toBeTruthy());
    expect(screen.queryByText("مقایسه با دوره قبل")).toBeNull();
  });

  it("reloads when the period changes and skips comparison for all time", async () => {
    const user = userEvent.setup();
    mockedApi.getAnalytics.mockResolvedValue(overview(2));
    mockedApi.getAnalyticsComparison.mockResolvedValue(comparison());
    render(<AnalyticsSection />);
    await waitFor(() => expect(screen.getByText("مقایسه با دوره قبل")).toBeTruthy());
    const select = screen.getByLabelText("تحلیل تمرین") as HTMLSelectElement;
    await user.selectOptions(select, "all");
    await waitFor(() =>
      expect(mockedApi.getAnalytics).toHaveBeenCalledWith({ period: "all" }),
    );
    expect(mockedApi.getAnalyticsComparison).not.toHaveBeenCalledWith({ period: "all" });
  });

  it("shows an error with retry", async () => {
    const user = userEvent.setup();
    mockedApi.getAnalytics.mockRejectedValueOnce(new Error("boom"));
    mockedApi.getAnalytics.mockResolvedValue(overview(1));
    mockedApi.getAnalyticsComparison.mockResolvedValue(comparison());
    render(<AnalyticsSection />);
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    await user.click(screen.getByText("تلاش دوباره"));
    await waitFor(() => expect(screen.getByText("روند روزانه")).toBeTruthy());
  });
});
