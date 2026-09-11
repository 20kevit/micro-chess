import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TrappedPiecesPage } from "../../pages/TrappedPiecesPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle, SpeedReport } from "../../api/types";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
import { api } from "../../api/client";

const mockedApi = vi.mocked(api, true);

// Corner-trapped knight position: Na1 boxed by own pawns b3/c2.
const FEN = "4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1";

function puzzle(id: number, prompt: string, withHint = false): Puzzle {
  return {
    id,
    exercise_slug: "trapped-pieces",
    fen: FEN,
    position_json: { fen: FEN, mode: "standard" },
    hint_json: withHint ? { hints: [{ id: "h1", text_fa: "متن راهنمایی" }] } : { hints: [] },
    prompt_fa: prompt,
    explanation: "",
    initial_rating: 900,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number, result: AttemptResponse["result"], score: number): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "trapped-pieces",
    mode: "practice",
    result,
    score,
    feedback_key: result === "correct" ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: { correct: ["a1"], missed: ["c8"], wrong: ["h1"] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/trapped-pieces?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/trapped-pieces" element={<TrappedPiecesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // Safe defaults: unmount cleanup finishes open sessions best-effort.
  mockedApi.finishTrappedSpeedSession = vi.fn().mockResolvedValue({
    session_id: "none",
    exercise_slug: "trapped-pieces",
    status: "finished",
    duration_s: 60,
    started_at: new Date().toISOString(),
    expires_at: new Date().toISOString(),
    remaining_ms: 0,
    buffered: 0,
    attempted: 0,
    correct: 0,
    partial: 0,
    wrong: 0,
    score: 0,
  });
});

describe("catalog direct entry", () => {
  it("trapped-pieces exposes practice and speed entries", () => {
    const meta = getExerciseMeta("trapped-pieces");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/trapped-pieces");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("mode entries point at distinct mode URLs", () => {
    const meta = getExerciseMeta("trapped-pieces");
    const urls = new Set((meta?.modes ?? []).map((m) => `${meta?.route}${m.params}`));
    expect(urls).toEqual(
      new Set(["/exercises/trapped-pieces?mode=practice", "/exercises/trapped-pieces?mode=speed"]),
    );
  });
});

describe("practice multi-selection", () => {
  it("?mode=practice enters practice directly with the first puzzle", async () => {
    mockedApi.nextTrappedPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال تمرینی؟"));
    renderPage("practice");
    expect(await screen.findByText("سؤال تمرینی؟")).toBeTruthy();
    expect(screen.queryByText("شروع تمرین‌ها")).toBeNull();
  });

  it("nothing is highlighted before submission and answers are not revealed", async () => {
    const user = userEvent.setup();
    mockedApi.nextTrappedPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال هدف؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "partial", 1));
    renderPage("practice");
    expect(await screen.findByText("سؤال هدف؟")).toBeTruthy();

    // The whole board is the question: no sky target ring anywhere.
    expect(screen.getByRole("gridcell", { name: "a1" }).className).not.toContain("outline-sky-400");
    // An answer square is NOT pre-marked (no answer leak in UI state).
    expect(screen.getByRole("gridcell", { name: "a1" }).className).not.toContain("outline-green-500");
    expect(screen.getByRole("gridcell", { name: "a1" }).className).not.toContain("outline-amber-500");

    // Multi-select toggles correctly (order-free set semantics).
    const a1 = screen.getByRole("gridcell", { name: "a1" });
    await user.click(a1);
    expect(a1.getAttribute("aria-pressed")).toBe("true");
    await user.click(a1);
    expect(a1.getAttribute("aria-pressed")).toBe("false");
    await user.click(a1);
    await user.click(screen.getByRole("gridcell", { name: "c8" }));

    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        puzzle_id: 1,
        answer: { selected_squares: ["a1", "c8"] },
        mode: "practice",
      }),
    );
    // Submission never ships the expected solution.
    const sentAnswer = (mockedApi.submitAttempt as ReturnType<typeof vi.fn>).mock.calls[0][0].answer;
    expect(sentAnswer).not.toHaveProperty("squares");
  });

  it("feedback colors distinguish correct/missed/wrong", async () => {
    const user = userEvent.setup();
    mockedApi.nextTrappedPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال رنگ؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "partial", 1));
    renderPage("practice");
    expect(await screen.findByText("سؤال رنگ؟")).toBeTruthy();
    await user.click(screen.getByRole("gridcell", { name: "a1" }));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    await screen.findByTestId("feedback");
    // Green = correct selected, orange = missed, red = wrong selected.
    expect(screen.getByRole("gridcell", { name: "a1" }).className).toContain("outline-green-500");
    expect(screen.getByRole("gridcell", { name: "c8" }).className).toContain("outline-amber-500");
    expect(screen.getByRole("gridcell", { name: "h1" }).className).toContain("outline-red-500");
  });

  it("practice progresses to the prefetched next puzzle", async () => {
    const user = userEvent.setup();
    mockedApi.nextTrappedPracticePuzzle = vi
      .fn()
      .mockResolvedValueOnce(puzzle(1, "سؤال اول؟"))
      .mockResolvedValueOnce(puzzle(2, "سؤال دوم؟"))
      .mockResolvedValue(puzzle(3, "سؤال سوم؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال اول؟")).toBeTruthy();
    await user.click(screen.getByRole("gridcell", { name: "a1" }));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "معمای بعدی" }));
    expect(screen.getByText("سؤال دوم؟")).toBeTruthy();
  });
});

describe("speed tap-to-submit", () => {
  function mockActiveBoot(batch: Puzzle[], sessionId: string) {
    mockedApi.startTrappedSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "trapped-pieces",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareTrappedSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startTrappedSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "trapped-pieces",
      status: "active",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 60000).toISOString(),
      remaining_ms: 60000,
      buffered: batch.length,
    });
  }

  function mockSubmitOk(sessionId: string) {
    let n = 0;
    mockedApi.submitTrappedSpeedAnswer = vi.fn().mockImplementation(async (_sid: string, body: { puzzle_id: number }) => {
      n += 1;
      return {
        attempt: attempt(body.puzzle_id, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["a1"], missed: [], wrong: [] },
        session: {
          session_id: sessionId,
          exercise_slug: "trapped-pieces",
          status: "active",
          duration_s: 60,
          started_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 59000).toISOString(),
          remaining_ms: 59000,
          buffered: 20,
          attempted: n,
          correct: n,
          partial: 0,
          wrong: 0,
          score: 5 * n,
        },
      };
    });
  }

  async function flushBoot() {
    for (let i = 0; i < 6; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
    }
  }

  it("?mode=speed prepares a 20-puzzle buffer before starting the clock", async () => {
    const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `سؤال ${i + 1}؟`));
    mockActiveBoot(batch, "s1");
    renderPage("speed");
    expect(await screen.findByText("در حال آماده‌سازی...")).toBeTruthy();
    expect(await screen.findByText("سؤال 1؟")).toBeTruthy();
    expect(mockedApi.prepareTrappedSpeedPuzzles).toHaveBeenCalledWith("s1", { count: 20 });
    expect(mockedApi.startTrappedSpeedClock).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("زمان باقی‌مانده")).toBeTruthy();
  });

  it("one tap submits immediately with no confirm button", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `پی ${i + 1}؟`));
      mockActiveBoot(batch, "tap1");
      mockSubmitOk("tap1");

      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("پی 1؟")).toBeTruthy();

      // No confirm button anywhere in Speed Mode: one tap submits.
      expect(screen.queryByRole("button", { name: "بررسی جواب" })).toBeNull();

      fireEvent.pointerDown(screen.getByRole("gridcell", { name: "a1" }));
      await act(async () => {});
      expect(mockedApi.submitTrappedSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(mockedApi.submitTrappedSpeedAnswer).toHaveBeenLastCalledWith(
        "tap1",
        expect.objectContaining({ puzzle_id: 1, answer: { selected_squares: ["a1"] } }),
      );
      expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
      expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      // Auto-advanced with selection reset; timer still visible.
      expect(screen.getByText("پی 2؟")).toBeTruthy();
      expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("false");
      expect(screen.getByText("زمان باقی‌مانده")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("expired session shows the authoritative per-puzzle report", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) =>
        puzzle(i + 1, i === 0 ? "تند اول؟" : `تند ${i + 1}؟`),
      );
      mockActiveBoot(batch, "s9");
      mockedApi.submitTrappedSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: attempt(1, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["a1"], missed: [], wrong: [] },
        session: {
          session_id: "s9",
          exercise_slug: "trapped-pieces",
          status: "active",
          duration_s: 60,
          started_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 59000).toISOString(),
          remaining_ms: 59000,
          buffered: 2,
          attempted: 1,
          correct: 1,
          partial: 0,
          wrong: 0,
          score: 5,
        },
      });
      const report: SpeedReport = {
        session: {
          session_id: "s9",
          exercise_slug: "trapped-pieces",
          status: "finished",
          duration_s: 60,
          started_at: new Date().toISOString(),
          expires_at: new Date().toISOString(),
          remaining_ms: 0,
          buffered: 2,
          attempted: 1,
          correct: 1,
          partial: 1,
          wrong: 0,
          score: 5,
        },
        entries: [
          {
            attempt_id: 10,
            puzzle_id: 1,
            prompt_fa: "تند اول؟",
            fen: FEN,
            result: "correct",
            score: 5,
            correct: ["a1"],
            missed: [],
            wrong: [],
            created_at: new Date().toISOString(),
          },
        ],
      };
      mockedApi.finishTrappedSpeedSession = vi.fn().mockResolvedValue(report.session);
      mockedApi.getTrappedSpeedReport = vi.fn().mockResolvedValue(report);

      renderPage("speed");
      expect(screen.getByText("در حال آماده‌سازی...")).toBeTruthy();
      for (let i = 0; i < 6; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(50);
        });
      }
      expect(screen.getByText("تند اول؟")).toBeTruthy();

      fireEvent.pointerDown(screen.getByRole("gridcell", { name: "a1" }));
      await act(async () => {});
      expect(mockedApi.submitTrappedSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      expect(screen.getByText("تند 2؟")).toBeTruthy();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(61000);
      });
      expect(screen.getByText("نتیجه سرعتی")).toBeTruthy();
      const containing = (text: string) => (_: string | null, el: Element | null) =>
        el?.tagName === "LI" && (el.textContent ?? "").includes(text);
      expect(screen.getByText(containing("تند اول؟"))).toBeTruthy();
      expect(mockedApi.getTrappedSpeedReport).toHaveBeenCalledWith("s9");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("gameplay chrome", () => {
  it("practice shows question, board, and submit together", async () => {
    const user = userEvent.setup();
    mockedApi.nextTrappedPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال چینش؟"));
    renderPage("practice");
    expect(await screen.findByTestId("question")).toBeTruthy();
    expect(screen.getByTestId("chessboard")).toBeTruthy();
    expect(screen.getByTestId("submit-bar")).toBeTruthy();
    expect(screen.getByText("سؤال چینش؟")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
  });

  it("hint is a compact ؟ button that reveals help without navigation", async () => {
    const user = userEvent.setup();
    mockedApi.nextTrappedPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال راهنما؟", true));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال راهنما؟")).toBeTruthy();
    const hintButton = screen.getByRole("button", { name: "راهنمایی" });
    expect(hintButton.textContent).toContain("؟");
    await user.click(hintButton);
    await user.click(screen.getByRole("button", { name: "نمایش راهنمایی" }));
    expect(screen.getByText("متن راهنمایی")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({ hints_used: ["h1"] }),
    );
  });
});
