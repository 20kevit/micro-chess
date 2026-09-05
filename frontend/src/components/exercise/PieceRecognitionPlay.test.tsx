import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PieceRecognitionPage } from "../../pages/PieceRecognitionPage";
import type { AttemptResponse, Puzzle, SpeedReport } from "../../api/types";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
import { api } from "../../api/client";

const mockedApi = vi.mocked(api, true);

const STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function puzzle(id: number, prompt: string): Puzzle {
  return {
    id,
    exercise_slug: "piece-recognition",
    fen: STARTPOS,
    position_json: {},
    hint_json: { hints: [] },
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
    exercise_slug: "piece-recognition",
    mode: "practice",
    result,
    score,
    feedback_key: result === "correct" ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail: { correct: ["e2"], missed: [], wrong: [] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/piece-recognition?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/piece-recognition" element={<PieceRecognitionPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // Safe defaults: unmount cleanup finishes open sessions best-effort.
  mockedApi.finishSpeedSession = vi.fn().mockResolvedValue({
    session_id: "none",
    exercise_slug: "piece-recognition",
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

describe("mode navigation", () => {
  it("?mode=practice enters practice directly with the first puzzle", async () => {
    mockedApi.nextPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال تمرینی؟"));
    renderPage("practice");
    expect(await screen.findByText("سؤال تمرینی؟")).toBeTruthy();
    // No intermediate mode screen: no second start button.
    expect(screen.queryByText("شروع تمرین‌ها")).toBeNull();
  });

  it("?mode=speed prepares a 20-puzzle buffer before starting the clock", async () => {
    const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `سؤال ${i + 1}؟`));
    mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
      session_id: "s1",
      exercise_slug: "piece-recognition",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
      session_id: "s1",
      exercise_slug: "piece-recognition",
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
    expect(mockedApi.prepareSpeedPuzzles).toHaveBeenCalledWith("s1", { count: 20 });
    expect(mockedApi.startSpeedClock).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("زمان باقی‌مانده")).toBeTruthy();
  });
});

describe("practice selection and submit", () => {
  it("select, deselect, multi-select, empty submit, fast feedback, instant next", async () => {
    const user = userEvent.setup();
    mockedApi.nextPracticePuzzle = vi
      .fn()
      .mockResolvedValueOnce(puzzle(1, "سؤال اول؟"))
      .mockResolvedValueOnce(puzzle(2, "سؤال دوم؟"))
      .mockResolvedValue(puzzle(3, "سؤال سوم؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 40));
    renderPage("practice");
    expect(await screen.findByText("سؤال اول؟")).toBeTruthy();

    const e2 = screen.getByRole("gridcell", { name: "e2" });
    await user.click(e2);
    expect(e2.getAttribute("aria-pressed")).toBe("true");
    await user.click(e2);
    expect(e2.getAttribute("aria-pressed")).toBe("false");
    await user.click(e2);
    await user.click(screen.getByRole("gridcell", { name: "e4" }));

    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        puzzle_id: 1,
        answer: { selected_squares: ["e2", "e4"] },
        mode: "practice",
      }),
    );
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();

    // Next puzzle was prefetched: transition is immediate.
    await user.click(screen.getByRole("button", { name: "معمای بعدی" }));
    expect(screen.getByText("سؤال دوم؟")).toBeTruthy();
  });

  it("empty selection submits and zero-target feedback shows +5", async () => {
    const user = userEvent.setup();
    mockedApi.nextPracticePuzzle = vi.fn().mockResolvedValue(puzzle(9, "سؤال خالی؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(9, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال خالی؟")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({ answer: { selected_squares: [] } }),
    );
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    expect(screen.getByText("۵ امتیاز")).toBeTruthy();
  });
});

describe("speed session recovery", () => {
  function apiError(status: number, detail: string) {
    return Object.assign(new Error(`api_error:${status}:${detail}`), { status, detail });
  }

  function mockBoot(batch: Puzzle[], sessionId = "sx") {
    mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "piece-recognition",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "piece-recognition",
      status: "active",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 60000).toISOString(),
      remaining_ms: 60000,
      buffered: batch.length,
    });
  }

  async function bootComplete(firstPrompt: string) {
    for (let i = 0; i < 6; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
    }
    expect(screen.getByText(firstPrompt)).toBeTruthy();
  }

  it("lost session lands on a dead screen with retry instead of a 404 loop", async () => {
    vi.useFakeTimers();
    try {
      mockBoot(Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `گم ${i + 1}؟`)), "lost1");
      mockedApi.submitSpeedAnswer = vi.fn().mockRejectedValue(apiError(404, "session_not_found"));
      mockedApi.getSpeedReport = vi.fn().mockRejectedValue(apiError(404, "session_not_found"));

      renderPage("speed");
      await bootComplete("گم 1؟");

      fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
      await act(async () => {});
      expect(mockedApi.submitSpeedAnswer).toHaveBeenCalledTimes(1);
      // Dead screen: dedicated message + fresh-start retry, no stuck puzzle.
      expect(screen.getByText("ارتباط با جلسه سرعتی قطع شد. یک دور جدید شروع کن.")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
      await act(async () => {});
      expect(mockedApi.startSpeedSession).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("ungradeable puzzle is skipped automatically", async () => {
    vi.useFakeTimers();
    try {
      mockBoot(Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `رد ${i + 1}؟`)), "skip1");
      mockedApi.submitSpeedAnswer = vi
        .fn()
        .mockRejectedValueOnce(apiError(404, "puzzle_not_in_session"));

      renderPage("speed");
      await bootComplete("رد 1؟");

      fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
      await act(async () => {});
      // Skipped forward to the queued puzzle with no error screen.
      expect(screen.getByText("رد 2؟")).toBeTruthy();
      expect(screen.queryByText("ارتباط با جلسه سرعتی قطع شد. یک دور جدید شروع کن.")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("repeated ungradeable puzzles give up to the dead screen", async () => {
    vi.useFakeTimers();
    try {
      mockBoot(Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `پایان ${i + 1}؟`)), "dead1");
      mockedApi.submitSpeedAnswer = vi.fn().mockRejectedValue(apiError(404, "puzzle_not_available"));
      mockedApi.getSpeedReport = vi.fn().mockRejectedValue(apiError(404, "session_not_found"));

      renderPage("speed");
      await bootComplete("پایان 1؟");

      for (let i = 0; i < 3; i++) {
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
      }
      expect(mockedApi.submitSpeedAnswer).toHaveBeenCalledTimes(3);
      expect(screen.getByText("ارتباط با جلسه سرعتی قطع شد. یک دور جدید شروع کن.")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed consecutive submissions", () => {
  function mockActiveBoot(batch: Puzzle[], sessionId: string) {
    mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "piece-recognition",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "piece-recognition",
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
    mockedApi.submitSpeedAnswer = vi.fn().mockImplementation(async (_sid: string, body: { puzzle_id: number }) => {
      n += 1;
      return {
        attempt: attempt(body.puzzle_id, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["e2"], missed: [], wrong: [] },
        session: {
          session_id: sessionId,
          exercise_slug: "piece-recognition",
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
        // Selection works: nothing is locked from the previous transition.
        // (The board listens to pointerdown; fireEvent.click alone never taps.)
        const e2 = screen.getByRole("gridcell", { name: "e2" });
        expect(e2.getAttribute("aria-pressed")).toBe("false");
        fireEvent.pointerDown(e2);
        expect(e2.getAttribute("aria-pressed")).toBe("true");

        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        // Correct puzzle id, no stale references, exactly one request.
        expect(mockedApi.submitSpeedAnswer).toHaveBeenCalledTimes(i);
        expect(mockedApi.submitSpeedAnswer).toHaveBeenLastCalledWith(
          "chain1",
          expect.objectContaining({ puzzle_id: i }),
        );
        expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
        // No manual next button anywhere in Speed Mode.
        expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();

        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        // Auto-advanced with selection reset.
        expect(screen.getByText(`پی ${i + 1}؟`)).toBeTruthy();
        expect(screen.getByRole("gridcell", { name: "e2" }).getAttribute("aria-pressed")).toBe(
          "false",
        );
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
      expect(mockedApi.prepareSpeedPuzzles).toHaveBeenCalledTimes(1);

      // Consume 8 puzzles: queue drops to 11 < 12, triggering background refill.
      for (let i = 1; i <= 8; i++) {
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        expect(screen.getByText(`صف ${i + 1}؟`)).toBeTruthy();
      }
      // Refilled proactively (second prepare call) while play never waited.
      expect(mockedApi.prepareSpeedPuzzles).toHaveBeenCalledTimes(2);
      expect(mockedApi.prepareSpeedPuzzles).toHaveBeenLastCalledWith("refill1", { count: 12 });
      expect(screen.getByText("زمان باقی‌مانده")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("failed background refill does not break the active session", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `پایدار ${i + 1}؟`));
      mockActiveBoot(batch, "steady1");
      mockedApi.prepareSpeedPuzzles = vi
        .fn()
        .mockResolvedValueOnce(batch)
        .mockRejectedValue(new Error("network down"));
      mockSubmitOk("steady1");

      renderPage("speed");
      await flushBoot();

      for (let i = 1; i <= 3; i++) {
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        expect(screen.getByText(`پایدار ${i + 1}؟`)).toBeTruthy();
      }
      // Current puzzle unaffected; no error screen from the failed refill.
      expect(screen.queryByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeNull();
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
      mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
        session_id: "gate1",
        exercise_slug: "piece-recognition",
        status: "preparing",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: null,
        remaining_ms: 60000,
        buffered: 0,
      });
      mockedApi.prepareSpeedPuzzles = vi.fn().mockReturnValue(gate);
      mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
        session_id: "gate1",
        exercise_slug: "piece-recognition",
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

describe("speed transition lock", () => {
  it("rapid repeated submit clicks send a single request", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `زود ${i + 1}؟`));
      mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
        session_id: "s7",
        exercise_slug: "piece-recognition",
        status: "preparing",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: null,
        remaining_ms: 60000,
        buffered: 0,
      });
      mockedApi.prepareSpeedPuzzles = vi.fn().mockResolvedValue(batch);
      mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
        session_id: "s7",
        exercise_slug: "piece-recognition",
        status: "active",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 60000).toISOString(),
        remaining_ms: 60000,
        buffered: 20,
      });
      mockedApi.submitSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: attempt(1, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["e2"], missed: [], wrong: [] },
        session: {
          session_id: "s7",
          exercise_slug: "piece-recognition",
          status: "active",
          duration_s: 60,
          started_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + 59000).toISOString(),
          remaining_ms: 59000,
          buffered: 20,
          attempted: 1,
          correct: 1,
          partial: 0,
          wrong: 0,
          score: 5,
        },
      });

      renderPage("speed");
      for (let i = 0; i < 6; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(50);
        });
      }
      expect(screen.getByText("زود 1؟")).toBeTruthy();

      const submit = screen.getByRole("button", { name: "بررسی جواب" });
      fireEvent.click(submit);
      fireEvent.click(submit);
      fireEvent.click(submit);
      await act(async () => {});
      expect(mockedApi.submitSpeedAnswer).toHaveBeenCalledTimes(1);
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
      mockedApi.startSpeedSession = vi.fn().mockResolvedValue({
        session_id: "s9",
        exercise_slug: "piece-recognition",
        status: "preparing",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: null,
        remaining_ms: 60000,
        buffered: 0,
      });
      mockedApi.prepareSpeedPuzzles = vi.fn().mockResolvedValue(batch);
      mockedApi.startSpeedClock = vi.fn().mockResolvedValue({
        session_id: "s9",
        exercise_slug: "piece-recognition",
        status: "active",
        duration_s: 60,
        started_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 60000).toISOString(),
        remaining_ms: 60000,
        buffered: 2,
      });
      mockedApi.submitSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: attempt(1, "correct", 5),
        feedback_key: "feedback.correct",
        detail: { correct: ["e2"], missed: [], wrong: [] },
        session: {
          session_id: "s9",
          exercise_slug: "piece-recognition",
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
          exercise_slug: "piece-recognition",
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
            fen: STARTPOS,
            result: "correct",
            score: 5,
            correct: ["e2"],
            missed: [],
            wrong: [],
            created_at: new Date().toISOString(),
          },
        ],
      };
      mockedApi.finishSpeedSession = vi.fn().mockResolvedValue(report.session);
      mockedApi.getSpeedReport = vi.fn().mockResolvedValue(report);

      renderPage("speed");
      expect(screen.getByText("در حال آماده‌سازی...")).toBeTruthy();
      // Fake timers: flush with act() instead of findBy/waitFor (their
      // internal timers never fire otherwise).
      for (let i = 0; i < 6; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(50);
        });
      }
      expect(screen.getByText("تند اول؟")).toBeTruthy();

      fireEvent.click(screen.getByRole("gridcell", { name: "e2" }));
      fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
      await act(async () => {});
      expect(mockedApi.submitSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(screen.getByText("آفرین! درست بود.")).toBeTruthy();
      // No manual next button in Speed Mode: feedback auto-advances.
      expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      expect(screen.getByText("تند 2؟")).toBeTruthy();

      // Let the authoritative clock run out: report comes from the server.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(61000);
      });
      expect(screen.getByText("نتیجه سرعتی")).toBeTruthy();
      const containing = (text: string) => (_: string | null, el: Element | null) =>
        el?.tagName === "LI" && (el.textContent ?? "").includes(text);
      expect(screen.getByText(containing("تند اول؟"))).toBeTruthy();
      expect(mockedApi.getSpeedReport).toHaveBeenCalledWith("s9");
    } finally {
      vi.useRealTimers();
    }
  });
});
