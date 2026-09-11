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
