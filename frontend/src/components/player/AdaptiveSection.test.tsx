import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { AdaptiveNext, AdaptiveOverview } from "../../api/types";
import { AdaptiveSection } from "./AdaptiveSection";

vi.mock("../../api/client", () => ({
  api: {
    adaptiveOverview: vi.fn(),
    adaptiveNext: vi.fn(),
    adaptiveOutcome: vi.fn(),
  },
  apiStatus: vi.fn(() => null),
}));

const mockedApi = vi.mocked(api, true);

function overview(): AdaptiveOverview {
  return {
    exercises: [
      {
        exercise: "piece-recognition",
        attempts: 5,
        accuracy: 0.2,
        recent_accuracy: 0.2,
        recent_failures: 4,
        repeated_mistakes: 2,
        avg_response_ms: null,
        days_since_last: 0,
        rating: null,
        provisional: null,
        games: 0,
        rating_trend: 0,
        reason: "RECENT_FAILURES",
      },
    ],
    recommended_exercise: "piece-recognition",
    reason: "RECENT_FAILURES",
  };
}

function nextItem(): AdaptiveNext {
  return {
    puzzle: {
      id: 7,
      exercise_slug: "piece-recognition",
      fen: null,
      position_json: {},
      hint_json: {},
      prompt_fa: "",
      explanation: "",
      initial_rating: 1000,
      is_published: true,
      is_archived: false,
    },
    reason: "RECENT_FAILURES",
    ability_rating: 1200,
    target_rating: 1000,
    observed_difficulty: "insufficient_data",
    recommendation_id: 3,
    fallback: false,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

function renderSection() {
  render(
    <MemoryRouter>
      <AdaptiveSection />
    </MemoryRouter>,
  );
}

describe("adaptive section", () => {
  it("shows a Persian loading state first", () => {
    mockedApi.adaptiveOverview.mockReturnValue(new Promise(() => {}));
    renderSection();
    expect(screen.getByText("تمرین تطبیقی")).toBeTruthy();
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
  });

  it("shows the recommended exercise with a Persian reason", async () => {
    mockedApi.adaptiveOverview.mockResolvedValue(overview());
    renderSection();
    await waitFor(() => expect(screen.getAllByText("تشخیص مهره")).toHaveLength(2));
    expect(screen.getAllByText("مرور بعد از اشتباه‌های اخیر").length).toBeGreaterThan(0);
    expect(screen.getByText("دریافت تمرین پیشنهادی")).toBeTruthy();
  });

  it("requests the next item and records accept on start", async () => {
    const user = userEvent.setup();
    mockedApi.adaptiveOverview.mockResolvedValue(overview());
    mockedApi.adaptiveNext.mockResolvedValue(nextItem());
    mockedApi.adaptiveOutcome.mockResolvedValue({
      id: 3,
      exercise_slug: "piece-recognition",
      puzzle_id: 7,
      reason: "RECENT_FAILURES",
      ability_rating: 1200,
      target_rating: 1000,
      seed: null,
      status: "accepted",
      result: null,
      created_at: "2026-09-11T00:00:00",
    });
    renderSection();
    await waitFor(() => expect(screen.getByText("دریافت تمرین پیشنهادی")).toBeTruthy());
    await user.click(screen.getByText("دریافت تمرین پیشنهادی"));
    await waitFor(() => expect(mockedApi.adaptiveNext).toHaveBeenCalledWith("piece-recognition"));
    await waitFor(() => expect(screen.getByText("شروع تمرین")).toBeTruthy());
    await user.click(screen.getByText("شروع تمرین"));
    await waitFor(() =>
      expect(mockedApi.adaptiveOutcome).toHaveBeenCalledWith(3, { status: "accepted" }),
    );
  });

  it("records skip and clears the suggestion", async () => {
    const user = userEvent.setup();
    mockedApi.adaptiveOverview.mockResolvedValue(overview());
    mockedApi.adaptiveNext.mockResolvedValue(nextItem());
    mockedApi.adaptiveOutcome.mockResolvedValue({
      id: 3,
      exercise_slug: "piece-recognition",
      puzzle_id: 7,
      reason: "RECENT_FAILURES",
      ability_rating: 1200,
      target_rating: 1000,
      seed: null,
      status: "skipped",
      result: null,
      created_at: "2026-09-11T00:00:00",
    });
    renderSection();
    await waitFor(() => expect(screen.getByText("دریافت تمرین پیشنهادی")).toBeTruthy());
    await user.click(screen.getByText("دریافت تمرین پیشنهادی"));
    await waitFor(() => expect(screen.getByText("رد کردن")).toBeTruthy());
    await user.click(screen.getByText("رد کردن"));
    await waitFor(() =>
      expect(mockedApi.adaptiveOutcome).toHaveBeenCalledWith(3, { status: "skipped" }),
    );
    await waitFor(() => expect(screen.queryByText("شروع تمرین")).toBeNull());
  });

  it("shows a Persian empty state when no content exists", async () => {
    mockedApi.adaptiveOverview.mockResolvedValue({ exercises: [], recommended_exercise: null, reason: null });
    renderSection();
    await waitFor(() =>
      expect(screen.getByText("محتوای تمرینی منتشرشده‌ای وجود ندارد.")).toBeTruthy(),
    );
  });

  it("shows a Persian error state with retry", async () => {
    const user = userEvent.setup();
    mockedApi.adaptiveOverview.mockRejectedValue(new Error("api_error:500"));
    renderSection();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    mockedApi.adaptiveOverview.mockResolvedValue(overview());
    await user.click(screen.getByText("تلاش دوباره"));
    await waitFor(() => expect(screen.getAllByText("تشخیص مهره").length).toBeGreaterThan(0));
  });
});
