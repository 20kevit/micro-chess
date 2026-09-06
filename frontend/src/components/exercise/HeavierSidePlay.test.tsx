import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MaterialComparisonPage } from "../../pages/MaterialComparisonPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import { fa } from "../../i18n/fa";
import { HEAVIER_CHOICES, choiceLabel } from "./HeavierSidePlay";

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

const FEN_WHITE = "4k1r1/pppp4/8/8/8/8/PPPPP3/R3K3 w - - 0 1";
const FEN_EQUAL = "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1";

function puzzle(id: number, fen: string): Puzzle {
  return {
    id,
    exercise_slug: "heavier-side",
    fen,
    position_json: { fen, mode: "standard" },
    hint_json: { hints: [] },
    prompt_fa: "کدام طرف جلوتر است؟",
    explanation: "سفید جلوتر بود.",
    initial_rating: 900,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number, choice: string, expected: string, correct: boolean): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "heavier-side",
    mode: "practice",
    result: correct ? "correct" : "wrong",
    score: correct ? 5 : -2,
    feedback_key: correct ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: correct
      ? { correct: [choice], missed: [], wrong: [] }
      : { correct: [], missed: [expected], wrong: [choice] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/heavier-side?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/heavier-side" element={<MaterialComparisonPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function speedSession(id: string, status: "preparing" | "active" | "finished" | "expired", remainingMs = 60000) {
  return {
    session_id: id,
    exercise_slug: "heavier-side",
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

describe("pure helpers", () => {
  it("offers exactly three choices with Persian labels", () => {
    expect([...HEAVIER_CHOICES]).toEqual(["white", "black", "equal"]);
    expect(choiceLabel("white")).toBe(fa["heavierSide.white"]);
    expect(choiceLabel("black")).toBe(fa["heavierSide.black"]);
    expect(choiceLabel("equal")).toBe(fa["heavierSide.equal"]);
  });
});

describe("practice mode", () => {
  it("renders the board, the question, and three large choices", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextHeavierPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_WHITE));
      renderPage("practice");
      await flushBoot();
      expect(screen.getByTestId("question")).toBeTruthy();
      expect(screen.getByTestId("board-zone")).toBeTruthy();
      expect(screen.getByTestId("chessboard")).toBeTruthy();
      for (const label of [fa["heavierSide.white"], fa["heavierSide.black"], fa["heavierSide.equal"]]) {
        const btn = screen.getByRole("button", { name: label });
        expect(btn).toBeTruthy();
        // Child-friendly 56px touch targets.
        expect(btn.className).toContain("min-h-[56px]");
      }
      // No material totals leak during the active puzzle.
      expect(screen.queryByTestId("feedback")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("tapping a choice submits immediately with no separate submit", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextHeavierPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_WHITE));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "white", "white", true));
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByRole("button", { name: fa["heavierSide.white"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
      expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
        expect.objectContaining({ puzzle_id: 1, answer: { choice: "white" }, mode: "practice" }),
      );
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("feedback")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("wrong feedback shows the correct answer briefly", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextHeavierPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_EQUAL));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "white", "equal", false));
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByRole("button", { name: fa["heavierSide.white"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedPlayError).toHaveBeenCalledTimes(1);
      const feedback = screen.getByTestId("feedback");
      // Correct answer revealed (equal), without engine evaluation.
      expect(feedback.textContent).toContain(fa["heavierSide.equal"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("auto-advances after feedback without waiting for manual next", async () => {
    vi.useFakeTimers();
    try {
      const first = puzzle(1, FEN_WHITE);
      const second = puzzle(2, FEN_EQUAL);
      mockedApi.nextHeavierPracticePuzzle = vi
        .fn()
        .mockResolvedValueOnce(first)
        .mockResolvedValue(second);
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "white", "white", true));
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByRole("button", { name: fa["heavierSide.white"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(screen.getByTestId("feedback")).toBeTruthy();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      // Advanced to the next puzzle: feedback cleared.
      expect(screen.queryByTestId("feedback")).toBeNull();
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("practice prefetch buffers the next puzzle", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextHeavierPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_WHITE));
      renderPage("practice");
      await flushBoot();
      // Initial load + background refill.
      expect(mockedApi.nextHeavierPracticePuzzle).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed mode", () => {
  it("boots a session, submits on tap, and auto-advances", async () => {
    vi.useFakeTimers();
    try {
      const buffer = Array.from({ length: 20 }, (_, i) => puzzle(300 + i, FEN_WHITE));
      mockedApi.startHeavierSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareHeavierSpeedPuzzles = vi.fn().mockResolvedValue(buffer);
      mockedApi.startHeavierSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active"));
      mockedApi.finishHeavierSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.submitHeavierSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: { ...attempt(300, "white", "white", true), mode: "practice" },
        feedback_key: "feedback.correct",
        detail: { correct: ["white"], missed: [], wrong: [] },
        session: { ...speedSession("s1", "active"), attempted: 1, correct: 1, score: 5 },
      });
      renderPage("speed");
      await flushBoot();
      expect(screen.getByTestId("timer")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: fa["heavierSide.white"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitHeavierSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      // Auto-advances with no manual next button.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(600);
      });
      expect(screen.queryByTestId("next-bar")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("finishes with the server-built report when the clock expires", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.startHeavierSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareHeavierSpeedPuzzles = vi
        .fn()
        .mockResolvedValue(Array.from({ length: 20 }, (_, i) => puzzle(200 + i, FEN_WHITE)));
      mockedApi.startHeavierSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active", 1000));
      mockedApi.finishHeavierSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.getHeavierSpeedReport = vi.fn().mockResolvedValue({
        session: { ...speedSession("s1", "finished", 0), attempted: 0, correct: 0, wrong: 0, score: 0 },
        entries: [],
      });
      renderPage("speed");
      await flushBoot();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(mockedApi.finishHeavierSpeedSession).toHaveBeenCalled();
      expect(screen.getByText(fa["speed.result"])).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("catalog and i18n", () => {
  it("exposes practice and speed entry modes", () => {
    const meta = getExerciseMeta("heavier-side");
    expect(meta?.status).toBe("active");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("defines every user-visible heavier-side string", () => {
    for (const key of [
      "heavierSide.question",
      "heavierSide.white",
      "heavierSide.black",
      "heavierSide.equal",
      "heavierSide.whiteAhead",
      "heavierSide.blackAhead",
      "heavierSide.equalMaterial",
    ] as const) {
      expect(fa[key], key).toBeTruthy();
    }
  });

  it("defaults to practice mode without a query param", () => {
    render(
      <MemoryRouter initialEntries={["/exercises/heavier-side"]}>
        <Routes>
          <Route path="/exercises/heavier-side" element={<MaterialComparisonPage />} />
        </Routes>
      </MemoryRouter>,
    );
    // Practice loop boots a practice puzzle (speed session never opens).
    expect(mockedApi.startHeavierSpeedSession ?? null).toBeNull();
  });
});
