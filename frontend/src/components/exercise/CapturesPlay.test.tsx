import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CapturesPage } from "../../pages/CapturesPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle, SpeedReport } from "../../api/types";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
import { api } from "../../api/client";

const mockedApi = vi.mocked(api, true);

// Hunter-vs-black position: white rook hunter on d4, black pawns on d5/h4.
const FEN = "8/8/8/3p4/3R3p/8/8/8 w - - 0 1";

function puzzle(id: number, prompt: string, withHint = false, from = "d4"): Puzzle {
  return {
    id,
    exercise_slug: "captures",
    fen: FEN,
    position_json: { from, profile: "ignore-enemy-attacks" },
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
    exercise_slug: "captures",
    mode: "practice",
    result,
    score,
    feedback_key: result === "correct" ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: { correct: ["e6"], missed: ["f5"], wrong: ["a1"] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/captures?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/captures" element={<CapturesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // Safe defaults: unmount cleanup finishes open sessions best-effort.
  mockedApi.finishCaptureSpeedSession = vi.fn().mockResolvedValue({
    session_id: "none",
    exercise_slug: "captures",
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
  it("captures exposes practice and speed entries", () => {
    const meta = getExerciseMeta("captures");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/captures");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("mode entries point at distinct mode URLs", () => {
    const meta = getExerciseMeta("captures");
    const urls = new Set((meta?.modes ?? []).map((m) => `${meta?.route}${m.params}`));
    expect(urls).toEqual(
      new Set(["/exercises/captures?mode=practice", "/exercises/captures?mode=speed"]),
    );
  });
});

describe("mode navigation", () => {
  it("?mode=practice enters practice directly with the first puzzle", async () => {
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال تمرینی؟"));
    renderPage("practice");
    expect(await screen.findByText("سؤال تمرینی؟")).toBeTruthy();
    // No intermediate mode screen: no second start button.
    expect(screen.queryByText("شروع تمرین‌ها")).toBeNull();
  });

  it("?mode=speed prepares a 20-puzzle buffer before starting the clock", async () => {
    const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `سؤال ${i + 1}؟`));
    mockedApi.startCaptureSpeedSession = vi.fn().mockResolvedValue({
      session_id: "s1",
      exercise_slug: "captures",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareCaptureSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startCaptureSpeedClock = vi.fn().mockResolvedValue({
      session_id: "s1",
      exercise_slug: "captures",
      status: "active",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 60000).toISOString(),
      remaining_ms: 60000,
      buffered: 20,
    });
    renderPage("speed");
    // Preparing state first: clock must not start before the buffer is ready.
    expect(await screen.findByText("در حال آماده‌سازی...")).toBeTruthy();
    expect(await screen.findByText("سؤال 1؟")).toBeTruthy();
    expect(mockedApi.prepareCaptureSpeedPuzzles).toHaveBeenCalledWith("s1", { count: 20 });
    expect(mockedApi.startCaptureSpeedClock).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("زمان باقی‌مانده")).toBeTruthy();
  });
});

describe("target highlight and selection", () => {
  it("target piece is highlighted before submission without revealing answers", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال هدف؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "partial", 7));
    renderPage("practice");
    expect(await screen.findByText("سؤال هدف؟")).toBeTruthy();

    // Only the target square carries the sky target ring pre-submission.
    const target = screen.getByRole("gridcell", { name: "d4" });
    expect(target.className).toContain("outline-sky-400");
    // A destination square is NOT pre-marked (no answer leak in UI state).
    expect(screen.getByRole("gridcell", { name: "e6" }).className).not.toContain("outline-green-500");
    expect(screen.getByRole("gridcell", { name: "e6" }).className).not.toContain("outline-amber-500");

    // Multi-select toggles correctly.
    const e6 = screen.getByRole("gridcell", { name: "e6" });
    await user.click(e6);
    expect(e6.getAttribute("aria-pressed")).toBe("true");
    await user.click(e6);
    expect(e6.getAttribute("aria-pressed")).toBe("false");
    await user.click(e6);
    await user.click(screen.getByRole("gridcell", { name: "f5" }));

    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        puzzle_id: 1,
        answer: { selected_squares: ["e6", "f5"] },
        mode: "practice",
      }),
    );
    // Submission never ships the expected solution.
    const sentAnswer = (mockedApi.submitAttempt as ReturnType<typeof vi.fn>).mock.calls[0][0].answer;
    expect(sentAnswer).not.toHaveProperty("squares");
  });

  it("feedback colors distinguish correct/missed/wrong", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال رنگ؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "partial", 7));
    renderPage("practice");
    expect(await screen.findByText("سؤال رنگ؟")).toBeTruthy();
    await user.click(screen.getByRole("gridcell", { name: "e6" }));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    await screen.findByTestId("feedback");
    // Green = correct selected, orange = missed, red = wrong selected.
    expect(screen.getByRole("gridcell", { name: "e6" }).className).toContain("outline-green-500");
    expect(screen.getByRole("gridcell", { name: "f5" }).className).toContain("outline-amber-500");
    expect(screen.getByRole("gridcell", { name: "a1" }).className).toContain("outline-red-500");
  });

  it("empty selection submits and zero-target feedback shows +5", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(9, "سؤال خالی؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue({ ...attempt(9, "correct", 5), detail: { correct: [], missed: [], wrong: [] } });
    renderPage("practice");
    expect(await screen.findByText("سؤال خالی؟")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({ answer: { selected_squares: [] } }),
    );
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    expect(screen.getByText("۵ امتیاز")).toBeTruthy();
  });

  it("practice progresses to the prefetched next puzzle", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi
      .fn()
      .mockResolvedValueOnce(puzzle(1, "سؤال اول؟"))
      .mockResolvedValueOnce(puzzle(2, "سؤال دوم؟"))
      .mockResolvedValue(puzzle(3, "سؤال سوم؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 40));
    renderPage("practice");
    expect(await screen.findByText("سؤال اول؟")).toBeTruthy();
    await user.click(screen.getByRole("gridcell", { name: "e6" }));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "معمای بعدی" }));
    expect(screen.getByText("سؤال دوم؟")).toBeTruthy();
  });
});

describe("speed consecutive submissions", () => {
  function mockActiveBoot(batch: Puzzle[], sessionId: string) {
    mockedApi.startCaptureSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "captures",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareCaptureSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startCaptureSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "captures",
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
    mockedApi.submitCaptureSpeedAnswer = vi.fn().mockImplementation(async (_sid: string, body: { puzzle_id: number }) => {
      n += 1;
      return {
        attempt: attempt(body.puzzle_id, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["e6"], missed: [], wrong: [] },
        session: {
          session_id: sessionId,
          exercise_slug: "captures",
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

  it("three consecutive puzzles each submit with fresh state", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `پی ${i + 1}؟`));
      mockActiveBoot(batch, "chain1");
      mockSubmitOk("chain1");

      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("پی 1؟")).toBeTruthy();

      for (let i = 1; i <= 3; i++) {
        const e6 = screen.getByRole("gridcell", { name: "e6" });
        expect(e6.getAttribute("aria-pressed")).toBe("false");
        fireEvent.pointerDown(e6);
        expect(e6.getAttribute("aria-pressed")).toBe("true");

        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        expect(mockedApi.submitCaptureSpeedAnswer).toHaveBeenCalledTimes(i);
        expect(mockedApi.submitCaptureSpeedAnswer).toHaveBeenLastCalledWith(
          "chain1",
          expect.objectContaining({ puzzle_id: i }),
        );
        expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
        // No manual next button anywhere in Speed Mode.
        expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();

        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        // Auto-advanced with selection reset; timer still visible.
        expect(screen.getByText(`پی ${i + 1}؟`)).toBeTruthy();
        expect(screen.getByRole("gridcell", { name: "e6" }).getAttribute("aria-pressed")).toBe("false");
        expect(screen.getByText("زمان باقی‌مانده")).toBeTruthy();
      }
    } finally {
      vi.useRealTimers();
    }
  });

  it("background refill keeps play continuous without loading states", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `صف ${i + 1}؟`));
      mockActiveBoot(batch, "refill1");
      mockSubmitOk("refill1");

      renderPage("speed");
      await flushBoot();
      expect(mockedApi.prepareCaptureSpeedPuzzles).toHaveBeenCalledTimes(1);

      for (let i = 1; i <= 8; i++) {
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        expect(screen.getByText(`صف ${i + 1}؟`)).toBeTruthy();
      }
      expect(mockedApi.prepareCaptureSpeedPuzzles).toHaveBeenCalledTimes(2);
      expect(mockedApi.prepareCaptureSpeedPuzzles).toHaveBeenLastCalledWith("refill1", { count: 12 });
      expect(screen.getByText("زمان باقی‌مانده")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("preparing UI hides internal buffer counts", async () => {
    vi.useFakeTimers();
    try {
      let resolvePrepare!: (value: Puzzle[]) => void;
      const gate = new Promise<Puzzle[]>((resolve) => {
        resolvePrepare = resolve;
      });
      mockedApi.startCaptureSpeedSession = vi.fn().mockResolvedValue({
        session_id: "gate1",
        exercise_slug: "captures",
        status: "preparing",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: null,
        remaining_ms: 60000,
        buffered: 0,
      });
      mockedApi.prepareCaptureSpeedPuzzles = vi.fn().mockReturnValue(gate);
      mockedApi.startCaptureSpeedClock = vi.fn().mockResolvedValue({
        session_id: "gate1",
        exercise_slug: "captures",
        status: "active",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 60000).toISOString(),
        remaining_ms: 60000,
        buffered: 20,
      });

      renderPage("speed");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(screen.getByText("در حال آماده‌سازی...")).toBeTruthy();
      const withCount = (_: string | null, el: Element | null) =>
        (el?.textContent ?? "").includes("۲۰");
      expect(screen.queryByText(withCount)).toBeNull();

      resolvePrepare(Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `دروازه ${i + 1}؟`)));
      await flushBoot();
      expect(screen.getByText("دروازه 1؟")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed expiry and report", () => {
  it("expired session shows the authoritative per-puzzle report", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) =>
        puzzle(i + 1, i === 0 ? "تند اول؟" : `تند ${i + 1}؟`),
      );
      mockedApi.startCaptureSpeedSession = vi.fn().mockResolvedValue({
        session_id: "s9",
        exercise_slug: "captures",
        status: "preparing",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: null,
        remaining_ms: 60000,
        buffered: 0,
      });
      mockedApi.prepareCaptureSpeedPuzzles = vi.fn().mockResolvedValue(batch);
      mockedApi.startCaptureSpeedClock = vi.fn().mockResolvedValue({
        session_id: "s9",
        exercise_slug: "captures",
        status: "active",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 60000).toISOString(),
        remaining_ms: 60000,
        buffered: 2,
      });
      mockedApi.submitCaptureSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: attempt(1, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["e6"], missed: [], wrong: [] },
        session: {
          session_id: "s9",
          exercise_slug: "captures",
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
          exercise_slug: "captures",
          status: "finished",
          duration_s: 60,
          started_at: new Date().toISOString(),
          expires_at: new Date().toISOString(),
          remaining_ms: 0,
          buffered: 2,
          attempted: 1,
          correct: 1,
          partial: 0,
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
            correct: ["e6"],
            missed: [],
            wrong: [],
            created_at: new Date().toISOString(),
          },
        ],
      };
      mockedApi.finishCaptureSpeedSession = vi.fn().mockResolvedValue(report.session);
      mockedApi.getCaptureSpeedReport = vi.fn().mockResolvedValue(report);

      renderPage("speed");
      expect(screen.getByText("در حال آماده‌سازی...")).toBeTruthy();
      for (let i = 0; i < 6; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(50);
        });
      }
      expect(screen.getByText("تند اول؟")).toBeTruthy();

      fireEvent.click(screen.getByRole("gridcell", { name: "e6" }));
      fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
      await act(async () => {});
      expect(mockedApi.submitCaptureSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
      expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();
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
      expect(mockedApi.getCaptureSpeedReport).toHaveBeenCalledWith("s9");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("gameplay chrome", () => {
  it("practice shows question, board, and submit together", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال چینش؟"));
    renderPage("practice");
    expect(await screen.findByTestId("question")).toBeTruthy();
    expect(screen.getByTestId("chessboard")).toBeTruthy();
    expect(screen.getByTestId("submit-bar")).toBeTruthy();
    expect(screen.getByText("سؤال چینش؟")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
  });

  it("hint is a compact ؟ button that reveals help without navigation", async () => {
    const user = userEvent.setup();
    mockedApi.nextCapturePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال راهنما؟", true));
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
