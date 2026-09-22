import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JourneyPage } from "./JourneyPage";
import { journeyApi, notifyApi } from "../api/client";
import type { TodayJourney } from "../api/types";

vi.mock("../api/client", () => ({
  journeyApi: { today: vi.fn(), startQuest: vi.fn(), completeQuest: vi.fn() },
  notifyApi: { track: vi.fn().mockResolvedValue(undefined) },
}));

const mocked = vi.mocked(journeyApi, true);

function journey(partial?: Partial<TodayJourney>): TodayJourney {
  return {
    local_date: "2026-09-21",
    timezone: "Asia/Tehran",
    completed_count: 0,
    total: 3,
    is_complete: false,
    quests: [
      {
        id: 1, slot: 1, kind: "core", title: "تمرین اصلی", description: "d",
        exercise_slug: "piece-recognition", puzzle_id: 10, target_count: 3,
        progress: 0, status: "pending", started_at: null, completed_at: null,
        local_date: "2026-09-21",
      },
      {
        id: 2, slot: 2, kind: "review", title: "مرور", description: "d",
        exercise_slug: "captures", puzzle_id: 11, target_count: 3,
        progress: 1, status: "started", started_at: "", completed_at: null,
        local_date: "2026-09-21",
      },
      {
        id: 3, slot: 3, kind: "challenge", title: "چالش", description: "d",
        exercise_slug: "trapped-pieces", puzzle_id: 12, target_count: 3,
        progress: 3, status: "completed", started_at: "", completed_at: "",
        local_date: "2026-09-21",
      },
    ],
    ...partial,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(notifyApi.track).mockResolvedValue(undefined);
});

describe("daily journey", () => {
  it("shows three quests, progress, and the obvious next action", async () => {
    mocked.today.mockResolvedValue(journey());
    render(
      <MemoryRouter>
        <JourneyPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("امروز ۳ مأموریت برایت آماده کرده‌ایم.")).toBeTruthy());
    expect(screen.getByText("تمرین اصلی")).toBeTruthy();
    expect(screen.getByText("مرور")).toBeTruthy();
    expect(screen.getByText("چالش")).toBeTruthy();
    expect(screen.getByRole("progressbar")).toBeTruthy();
    expect(screen.getByRole("button", { name: "شروع تمرین امروز" })).toBeTruthy();
  });

  it("shows the daily completion state when all quests are done", async () => {
    const done = journey({ completed_count: 3, is_complete: true });
    done.quests = done.quests.map((q) => ({ ...q, status: "completed" }));
    mocked.today.mockResolvedValue(done);
    render(
      <MemoryRouter>
        <JourneyPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("هر ۳ مأموریت امروز کامل شد!")).toBeTruthy());
    expect(screen.getAllByRole("button", { name: "تمرین بیشتر" }).length).toBeGreaterThan(0);
  });

  it("starts the next incomplete quest on CTA", async () => {
    const user = userEvent.setup();
    mocked.today.mockResolvedValue(journey());
    mocked.startQuest.mockResolvedValue(journey().quests[0]);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<JourneyPage />} />
          <Route path="/exercises/:slug" element={<p>play</p>} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "شروع تمرین امروز" })).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "شروع تمرین امروز" }));
    await waitFor(() => expect(mocked.startQuest).toHaveBeenCalledWith(1));
  });

  it("shows loading, error with retry, and empty states", async () => {
    mocked.today.mockRejectedValueOnce(new Error("down"));
    const { unmount } = render(
      <MemoryRouter>
        <JourneyPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    unmount();

    mocked.today.mockResolvedValueOnce(journey({ total: 0, quests: [] }));
    render(
      <MemoryRouter>
        <JourneyPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("مأموریتی برای امروز پیدا نشد؛ یک تمرین را خودت انتخاب کن.")).toBeTruthy(),
    );
  });
});
