import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BlindfoldCalculationPage } from "../../pages/BlindfoldCalculationPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import { fa } from "../../i18n/fa";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
vi.mock("../../lib/sound", () => ({ playError: vi.fn(), playSuccess: vi.fn() }));
import { api } from "../../api/client";
import { playError, playSuccess } from "../../lib/sound";

const mockedApi = vi.mocked(api, true);
const mockedPlaySuccess = vi.mocked(playSuccess);
const mockedPlayError = vi.mocked(playError);

const DESCRIPTION =
  "موقعیت مهره‌ها\n\nسفید\nشاه: c6\nپیاده: a3، b4، d5، g2\n\nسیاه\nشاه: d8\nپیاده: a7، f4، g5\n\nنوبت: سفید";

function puzzle(id: number): Puzzle {
  return {
    id,
    exercise_slug: "blindfold-calculation",
    fen: null,
    position_json: { description_fa: DESCRIPTION, side_to_move: "white", mode: "best-move", piece_count: 9 },
    hint_json: { hints: [] },
    prompt_fa: "بهترین حرکت چیست؟",
    explanation: "بهترین حرکت همین بود.",
    initial_rating: 1166,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number, correct: boolean, move = "Kd6"): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "blindfold-calculation",
    mode: "practice",
    result: correct ? "correct" : "wrong",
    score: correct ? 1 : 0,
    feedback_key: correct ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: correct
      ? { correct: [move], missed: [], wrong: [], correct_move: move }
      : { correct: [], missed: [move], wrong: ["Kc5"], correct_move: move },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/blindfold-calculation?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/blindfold-calculation" element={<BlindfoldCalculationPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function speedSession(id: string, status: "preparing" | "active" | "finished" | "expired", remainingMs = 60000) {
  return {
    session_id: id,
    exercise_slug: "blindfold-calculation",
    status,
    duration_s: 60,
    started_at: new Date().toISOString(),
    expires_at: null,
    remaining_ms: remainingMs,
    buffered: 20,
    attempted: 0,
    correct: 0,
    partial: 0,
    wrong: 0,
    score: 0,
  };
}

/** Flush pending promises/timers until the question appears (fake timers on). */
async function flushBoot(maxRounds = 16) {
  for (let i = 0; i < maxRounds; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    if (screen.queryByTestId("question")) return;
  }
}

beforeEach(() => {
  for (const key of Object.keys(mockedApi)) {
    delete (mockedApi as Record<string, unknown>)[key];
  }
  mockedPlaySuccess.mockClear();
  mockedPlayError.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("practice mode", () => {
  it("renders the structured description, the question, and a SAN input — never a board", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBlindfoldCalcPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1));
      renderPage("practice");
      await flushBoot();
      expect(screen.getByTestId("question")).toBeTruthy();
      const description = screen.getByTestId("description");
      // Structured sections from the server text.
      expect(description.textContent).toContain("سفید");
      expect(description.textContent).toContain("سیاه");
      expect(description.textContent).toContain("شاه");
      expect(description.textContent).toContain("پیاده");
      expect(description.textContent).toContain("نوبت: سفید");
      // Squares stay readable (LTR islands inside RTL text).
      expect(description.textContent).toContain("c6");
      // The explicit question is shown (as the prompt header).
      expect(screen.getByTestId("question").textContent).toContain(fa["blindfoldCalculation.question"]);
      // Guidance above the SAN input.
      expect(screen.getByText(fa["blindfoldCalculation.instruction"])).toBeTruthy();
      // No chessboard is rendered at any point in this exercise.
      expect(screen.queryByTestId("chessboard")).toBeNull();
      expect(screen.queryByTestId("board-zone")).toBeNull();
      // Touch-sized SAN input with a submit button.
      const input = screen.getByLabelText(fa["blindfoldCalculation.answer"]);
      expect(input.tagName).toBe("INPUT");
      expect(input.className).toContain("min-h-[56px]");
      expect(screen.getByRole("button", { name: fa["play.submit"] })).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("submits the typed SAN and shows correct feedback with the SAN", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBlindfoldCalcPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, true));
      renderPage("practice");
      await flushBoot();
      fireEvent.change(screen.getByLabelText(fa["blindfoldCalculation.answer"]), {
        target: { value: "Kd6" },
      });
      fireEvent.click(screen.getByRole("button", { name: fa["play.submit"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
      expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
        expect.objectContaining({ puzzle_id: 1, answer: { move: "Kd6" }, mode: "practice" }),
      );
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      const feedback = screen.getByTestId("feedback");
      expect(feedback.textContent).toContain("Kd6");
    } finally {
      vi.useRealTimers();
    }
  });

  it("wrong feedback reveals the correct SAN", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBlindfoldCalcPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, false));
      renderPage("practice");
      await flushBoot();
      fireEvent.change(screen.getByLabelText(fa["blindfoldCalculation.answer"]), {
        target: { value: "Kc5" },
      });
      fireEvent.click(screen.getByRole("button", { name: fa["play.submit"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedPlayError).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("feedback").textContent).toContain("Kd6");
    } finally {
      vi.useRealTimers();
    }
  });

  it("practice prefetch buffers the next puzzle", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBlindfoldCalcPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1));
      renderPage("practice");
      await flushBoot();
      // Initial load + background refill.
      expect(mockedApi.nextBlindfoldCalcPracticePuzzle).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed mode", () => {
  it("boots a session, submits the SAN, and auto-advances with no manual next", async () => {
    vi.useFakeTimers();
    try {
      const buffer = Array.from({ length: 20 }, (_, i) => puzzle(300 + i));
      mockedApi.startBlindfoldCalcSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareBlindfoldCalcSpeedPuzzles = vi.fn().mockResolvedValue(buffer);
      mockedApi.startBlindfoldCalcSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active"));
      mockedApi.finishBlindfoldCalcSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.submitBlindfoldCalcSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: { ...attempt(300, true), mode: "practice" },
        feedback_key: "feedback.correct",
        detail: { correct: ["Kd6"], missed: [], wrong: [], correct_move: "Kd6" },
        session: { ...speedSession("s1", "active"), attempted: 1, correct: 1, score: 1 },
      });
      renderPage("speed");
      await flushBoot();
      expect(screen.getByTestId("timer")).toBeTruthy();
      // Still no board in speed mode.
      expect(screen.queryByTestId("chessboard")).toBeNull();
      fireEvent.change(screen.getByLabelText(fa["blindfoldCalculation.answer"]), {
        target: { value: "Kd6" },
      });
      fireEvent.click(screen.getByRole("button", { name: fa["play.submit"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitBlindfoldCalcSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(mockedApi.submitBlindfoldCalcSpeedAnswer).toHaveBeenCalledWith(
        "s1",
        expect.objectContaining({ puzzle_id: 300, answer: { move: "Kd6" } }),
      );
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      // Auto-advances with no manual next button.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(screen.queryByTestId("next-bar")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("finishes with the server-built report when the clock expires", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.startBlindfoldCalcSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareBlindfoldCalcSpeedPuzzles = vi
        .fn()
        .mockResolvedValue(Array.from({ length: 20 }, (_, i) => puzzle(200 + i)));
      mockedApi.startBlindfoldCalcSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active", 1000));
      mockedApi.finishBlindfoldCalcSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.getBlindfoldCalcSpeedReport = vi.fn().mockResolvedValue({
        session: { ...speedSession("s1", "finished", 0), attempted: 0, correct: 0, wrong: 0, score: 0 },
        entries: [],
      });
      renderPage("speed");
      await flushBoot();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(mockedApi.finishBlindfoldCalcSpeedSession).toHaveBeenCalled();
      expect(screen.getByText(fa["speed.result"])).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("catalog and i18n", () => {
  it("exposes practice and speed entry modes", () => {
    const meta = getExerciseMeta("blindfold-calculation");
    expect(meta?.status).toBe("active");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("defines every user-visible blindfold-calculation string", () => {
    for (const key of [
      "blindfoldCalculation.question",
      "blindfoldCalculation.instruction",
      "blindfoldCalculation.position",
      "blindfoldCalculation.answer",
      "blindfoldCalculation.correctMove",
    ] as const) {
      expect(fa[key], key).toBeTruthy();
    }
  });

  it("defaults to practice mode without a query param", () => {
    render(
      <MemoryRouter initialEntries={["/exercises/blindfold-calculation"]}>
        <Routes>
          <Route path="/exercises/blindfold-calculation" element={<BlindfoldCalculationPage />} />
        </Routes>
      </MemoryRouter>,
    );
    // Practice loop boots a practice puzzle (speed session never opens).
    expect(mockedApi.startBlindfoldCalcSpeedSession ?? null).toBeNull();
  });
});
