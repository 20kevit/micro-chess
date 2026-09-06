import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChineseBoardPage } from "../../pages/ChineseBoardPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import { fa } from "../../i18n/fa";
import { memorizeMsOf } from "./ChineseBoardPlay";

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

const FEN_SMALL = "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1";

function puzzle(id: number, fen: string, memorizationMs = 1200): Puzzle {
  return {
    id,
    exercise_slug: "chinese-board",
    fen,
    position_json: { fen, piece_count: 4, memorization_ms: memorizationMs, mode: "standard" },
    hint_json: { hints: [] },
    prompt_fa: "این صفحه را حفظ کن و بعد از نو بچین.",
    explanation: "این صفحه 4 مهره داشت.",
    initial_rating: 900,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number, correct: boolean, score: number): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "chinese-board",
    mode: "practice",
    result: correct ? "correct" : "wrong",
    score,
    feedback_key: correct ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: correct
      ? {
          correct: ["black:K@e8", "black:Q@d8", "white:K@e1", "white:Q@d1"],
          missed: [],
          wrong: [],
          missing: [],
          extra: [],
          correct_squares: ["d1", "d8", "e1", "e8"],
          missed_squares: [],
          wrong_squares: [],
          piece_count: 4,
          memorization_ms: 1200,
        }
      : {
          correct: ["black:Q@d8", "white:K@e1", "white:Q@d1"],
          missed: ["black:K@e8"],
          wrong: ["black:K@e8"],
          missing: ["black:K@e8"],
          extra: [],
          correct_squares: ["d1", "d8", "e1"],
          missed_squares: ["e8"],
          wrong_squares: ["e7"],
          piece_count: 4,
          memorization_ms: 1200,
        },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/chinese-board?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/chinese-board" element={<ChineseBoardPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function speedSession(id: string, status: "preparing" | "active" | "finished" | "expired", remainingMs = 60000) {
  return {
    session_id: id,
    exercise_slug: "chinese-board",
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

/** Tap a board square. ChessBoard handles press via pointerdown, so a
 * plain click event never reaches onSquarePress. */
function tap(square: string) {
  fireEvent.pointerDown(screen.getByRole("gridcell", { name: square }));
}

/** Flush pending promises until the memorize phase appears (fake timers on). */
async function flushMemorize(maxRounds = 16) {
  for (let i = 0; i < maxRounds; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    if (screen.queryByTestId("memorize-progress")) return;
  }
}

/** Advance past the study budget plus the fade transition. */
async function finishMemorizing(budgetMs: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(budgetMs + 400);
  });
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

describe("catalog and i18n", () => {
  it("registers chinese-board with practice and speed entries", () => {
    const meta = getExerciseMeta("chinese-board");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/chinese-board");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("uses the صفحه چینی title, never صفحه حفظی", () => {
    expect(fa["chineseBoard.title"]).toBe("صفحه چینی");
    expect(fa["exercises.chinese-board.title"]).toBe("صفحه چینی");
    expect(fa["chineseBoard.check"]).toBe("بررسی صفحه");
  });

  it("memorize budget comes from the server payload", () => {
    expect(memorizeMsOf(puzzle(1, FEN_SMALL, 3000))).toBe(3000);
    expect(memorizeMsOf(puzzle(1, FEN_SMALL, 9600))).toBe(9600);
    // piece_count fallback: count * 300.
    const noBudget = { ...puzzle(1, FEN_SMALL), position_json: { piece_count: 10 } };
    expect(memorizeMsOf(noBudget)).toBe(3000);
  });
});

describe("practice mode", () => {
  it("shows the position read-only with a countdown, no palette yet", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      renderPage("practice");
      await flushMemorize();
      expect(screen.getByTestId("memorize-progress")).toBeTruthy();
      expect(screen.getByTestId("chessboard")).toBeTruthy();
      // Memorized pieces are visible (black king renders from the FEN).
      expect(screen.getByRole("gridcell", { name: "e8" }).innerHTML).toContain("bK");
      // No palette, no check button during memorization.
      expect(screen.queryByTestId("submit-bar")).toBeNull();
      expect(screen.queryByRole("button", { name: fa["chineseBoard.check"] })).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("clears the board after the budget and shows palette plus check", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      renderPage("practice");
      await flushMemorize();
      await finishMemorizing(1200);
      expect(screen.queryByTestId("memorize-progress")).toBeNull();
      expect(screen.getByTestId("submit-bar")).toBeTruthy();
      // Board is empty now.
      expect(screen.getByRole("gridcell", { name: "e8" }).innerHTML).not.toContain("bK");
      // Full 12-piece palette with accessible labels, plus eraser.
      expect(screen.getByRole("button", { name: "سفید وزیر" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "سیاه اسب" })).toBeTruthy();
      expect(screen.getByRole("button", { name: fa["memory.eraser"] })).toBeTruthy();
      expect(screen.getByRole("button", { name: fa["chineseBoard.check"] })).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("places, replaces, and erases pieces by tapping", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      renderPage("practice");
      await flushMemorize();
      await finishMemorizing(1200);
      fireEvent.click(screen.getByRole("button", { name: "سفید وزیر" }));
      tap("e4");
      expect(screen.getByRole("gridcell", { name: "e4" }).innerHTML).toContain("wQ");
      // Replace with the black knight on the same square.
      fireEvent.click(screen.getByRole("button", { name: "سیاه اسب" }));
      tap("e4");
      const html = screen.getByRole("gridcell", { name: "e4" }).innerHTML;
      expect(html).toContain("bN");
      expect(html).not.toContain("wQ");
      // Eraser removes it.
      fireEvent.click(screen.getByRole("button", { name: fa["memory.eraser"] }));
      tap("e4");
      expect(screen.getByRole("gridcell", { name: "e4" }).innerHTML).not.toContain("bN");
    } finally {
      vi.useRealTimers();
    }
  });

  it("checks the reconstruction with pieces only, never score or fen", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, false, 13));
      renderPage("practice");
      await flushMemorize();
      await finishMemorizing(1200);
      fireEvent.click(screen.getByRole("button", { name: "سفید وزیر" }));
      tap("d1");
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.check"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
      const body = vi.mocked(mockedApi.submitAttempt).mock.calls[0][0];
      expect(body.puzzle_id).toBe(1);
      expect(body.mode).toBe("practice");
      // The client submits ONLY the reconstruction — no score, no fen, no counts.
      expect(body.answer).toEqual({
        pieces: [{ square: "d1", piece: "Q", color: "white" }],
      });
      expect(mockedPlayError).toHaveBeenCalledTimes(1);
      const feedback = screen.getByTestId("feedback");
      expect(feedback.textContent).toContain(fa["chineseBoard.correct"]);
      expect(feedback.textContent).toContain(fa["chineseBoard.missing"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not auto-advance in practice; next loads the buffered puzzle", async () => {
    vi.useFakeTimers();
    try {
      const first = puzzle(1, FEN_SMALL);
      const second = puzzle(2, FEN_SMALL);
      mockedApi.nextChinesePracticePuzzle = vi
        .fn()
        .mockResolvedValueOnce(first)
        .mockResolvedValue(second);
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, true, 20));
      renderPage("practice");
      await flushMemorize();
      await finishMemorizing(1200);
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.check"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(screen.getByTestId("feedback")).toBeTruthy();
      // No auto-advance: still on the feedback after seconds pass.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(screen.getByTestId("feedback")).toBeTruthy();
      // Manual next swaps to the buffered puzzle (memorize phase again).
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.next"] }));
      await flushMemorize();
      expect(screen.getByTestId("memorize-progress")).toBeTruthy();
      expect(screen.queryByTestId("feedback")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("toggles between your answer and the correct board after submit", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, false, 13));
      renderPage("practice");
      await flushMemorize();
      await finishMemorizing(1200);
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.check"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(screen.getByTestId("yours-board")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.correctBoard"] }));
      expect(screen.getByTestId("answer-board")).toBeTruthy();
      // The correct board renders the memorized position (black king on e8).
      expect(screen.getByTestId("answer-board").innerHTML).toContain("bK");
    } finally {
      vi.useRealTimers();
    }
  });

  it("practice prefetch buffers the next puzzle", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextChinesePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, FEN_SMALL));
      renderPage("practice");
      await flushMemorize();
      expect(mockedApi.nextChinesePracticePuzzle).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed mode", () => {
  it("boots a session, memorizes, checks, and auto-advances", async () => {
    vi.useFakeTimers();
    try {
      const buffer = Array.from({ length: 20 }, (_, i) => puzzle(300 + i, FEN_SMALL, 500));
      mockedApi.startChineseSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareChineseSpeedPuzzles = vi.fn().mockResolvedValue(buffer);
      mockedApi.startChineseSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active"));
      mockedApi.finishChineseSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.submitChineseSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: { ...attempt(300, false, 13), mode: "practice" },
        feedback_key: "feedback.wrong",
        detail: attempt(300, false, 13).detail,
        session: { ...speedSession("s1", "active", 55000), attempted: 1, wrong: 1, score: 13 },
      });
      renderPage("speed");
      await flushMemorize();
      // Session prepared with the minimum buffer before the clock started.
      expect(mockedApi.prepareChineseSpeedPuzzles).toHaveBeenCalled();
      expect(mockedApi.startChineseSpeedClock).toHaveBeenCalledTimes(1);
      // Per-puzzle memorize phase still applies inside the 60s session.
      expect(screen.getByTestId("memorize-progress")).toBeTruthy();
      expect(screen.getByTestId("timer")).toBeTruthy();
      await finishMemorizing(500);
      expect(screen.getByTestId("submit-bar")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "سفید وزیر" }));
      tap("d1");
      fireEvent.click(screen.getByRole("button", { name: fa["chineseBoard.check"] }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitChineseSpeedAnswer).toHaveBeenCalledTimes(1);
      const body = vi.mocked(mockedApi.submitChineseSpeedAnswer).mock.calls[0][1];
      expect(body.answer).toEqual({ pieces: [{ square: "d1", piece: "Q", color: "white" }] });
      expect(screen.getByTestId("feedback")).toBeTruthy();
      // Brief feedback, then automatic transition to the next puzzle.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(700);
      });
      expect(screen.getByTestId("memorize-progress")).toBeTruthy();
      expect(screen.queryByTestId("feedback")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
