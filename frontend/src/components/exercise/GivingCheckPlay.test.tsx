import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GiveCheckPage } from "../../pages/GiveCheckPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import { answerForArrows, feedbackArrows, formatArrowUci, isPromotionArrow } from "./GivingCheckPlay";
import { fenToPieces } from "../../lib/fen";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
import { api } from "../../api/client";

const mockedApi = vi.mocked(api, true);

const QUEEN_FEN = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1";
const PROMO_FEN = "7k/6P1/8/8/8/8/8/4K3 w - - 0 1";

function puzzle(id: number, prompt: string, fen = QUEEN_FEN, withHint = false): Puzzle {
  return {
    id,
    exercise_slug: "give-check",
    fen,
    position_json: { fen },
    hint_json: withHint ? { hints: [{ id: "h1", text_fa: "متن راهنمایی" }] } : { hints: [] },
    prompt_fa: prompt,
    explanation: "",
    initial_rating: 900,
    is_published: true,
    is_archived: false,
  };
}

function attempt(
  puzzleId: number,
  result: AttemptResponse["result"],
  score: number,
  detail: AttemptResponse["detail"] = { correct: ["d4d8"], missed: ["d4h8"], wrong: ["e2e4"] },
): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "give-check",
    mode: "practice",
    result,
    score,
    feedback_key: result === "correct" ? "feedback.correct" : result === "partial" ? "feedback.partial" : "feedback.wrong",
    rating_delta: null,
    detail,
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/give-check?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/give-check" element={<GiveCheckPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// Board geometry: tests pin the board to an 800x800 rect at (0,0), so drag
// coordinates map to squares exactly like the production viewBox math.
function mockBoardRect() {
  return vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    width: 800,
    height: 800,
    top: 0,
    left: 0,
    right: 800,
    bottom: 800,
    toJSON: () => ({}),
  } as DOMRect);
}

function squareXY(square: string): { clientX: number; clientY: number } {
  const file = square.charCodeAt(0) - "a".charCodeAt(0);
  const rank = Number(square.slice(1));
  return {
    clientX: ((file + 0.5) / 8) * 800,
    clientY: ((8 - rank + 0.5) / 8) * 800,
  };
}

function drawArrow(from: string, to: string, pointerType = "mouse") {
  // Dispatch from the origin square: production pointer events target
  // squares/pieces and bubble up to the board's gesture layer, so the test
  // must start inside the grid, not on the outer wrapper.
  const origin = screen.getByRole("gridcell", { name: from });
  const start = squareXY(from);
  const end = squareXY(to);
  fireEvent.pointerDown(origin, { pointerType, button: 0, pointerId: 1, ...start });
  fireEvent.pointerMove(origin, { pointerType, button: 0, pointerId: 1, ...end });
  fireEvent.pointerUp(origin, { pointerType, button: 0, pointerId: 1, ...end });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useRealTimers();
  // Safe defaults: unmount cleanup finishes open sessions best-effort.
  mockedApi.finishGiveCheckSpeedSession = vi.fn().mockResolvedValue({
    session_id: "none",
    exercise_slug: "give-check",
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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("arrow payload helpers", () => {
  it("answerForArrows sends promotion only for pawn-to-last-rank moves", () => {
    const pieces = fenToPieces(PROMO_FEN);
    expect(
      answerForArrows(
        [
          { from: "g7", to: "g8", promotion: "q" },
          { from: "e1", to: "e2", promotion: "q" },
        ],
        pieces,
      ),
    ).toEqual({
      moves: [
        { from: "g7", to: "g8", promotion: "q" },
        { from: "e1", to: "e2" },
      ],
    });
  });

  it("isPromotionArrow detects pawns reaching the last rank", () => {
    const pieces = fenToPieces(PROMO_FEN);
    expect(isPromotionArrow(pieces, "g7", "g8")).toBe(true);
    expect(isPromotionArrow(pieces, "e1", "e2")).toBe(false);
    expect(isPromotionArrow(fenToPieces(QUEEN_FEN), "d4", "d8")).toBe(false);
  });

  it("feedbackArrows tones correct/missed/wrong and skips malformed", () => {
    const arrows = feedbackArrows(
      attempt(1, "partial", 2, { correct: ["d4d8"], missed: ["d4h8"], wrong: ["e2e4", "nope"] }),
    );
    expect(arrows).toEqual([
      { from: "d4", to: "d8", tone: "correct" },
      { from: "d4", to: "h8", tone: "missed" },
      { from: "e2", to: "e4", tone: "wrong" },
    ]);
  });

  it("formatArrowUci renders arrows, falls back to raw text", () => {
    expect(formatArrowUci("d4d8")).toBe("d4→d8");
    expect(formatArrowUci("g7g8q")).toBe("g7→g8q");
    expect(formatArrowUci("nope")).toBe("nope");
  });
});

describe("catalog direct entry", () => {
  it("give-check exposes practice and speed entries", () => {
    const meta = getExerciseMeta("give-check");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/give-check");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("mode entries point at distinct mode URLs", () => {
    const meta = getExerciseMeta("give-check");
    const urls = new Set((meta?.modes ?? []).map((m) => `${meta?.route}${m.params}`));
    expect(urls).toEqual(
      new Set(["/exercises/give-check?mode=practice", "/exercises/give-check?mode=speed"]),
    );
  });

  it("removed exercises are gone and castling sits at the end", async () => {
    const { EXERCISE_CATALOG } = await import("../../exercises/catalog");
    const slugs = EXERCISE_CATALOG.map((e) => e.slug);
    expect(slugs).not.toContain("hanging-pieces");
    expect(slugs).not.toContain("equal-attackers-defenders");
    expect(slugs.slice(0, 5)).toEqual([
      "piece-recognition",
      "legal-destinations",
      "captures",
      "undefended-pieces",
      "give-check",
    ]);
    expect(slugs[slugs.length - 1]).toBe("castling-rights");
  });
});

describe("practice arrow interaction", () => {
  it("?mode=practice enters practice directly with the first puzzle", async () => {
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "با کدام حرکت‌ها می‌توان کیش داد؟"));
    renderPage("practice");
    expect(await screen.findByText("با کدام حرکت‌ها می‌توان کیش داد؟")).toBeTruthy();
    expect(screen.queryByText("شروع تمرین‌ها")).toBeNull();
    expect(screen.getByTestId("chessboard")).toBeTruthy();
  });

  it("mouse drag draws an arrow and submits from->to", async () => {
    mockBoardRect();
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال فلش؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5, { correct: ["d4d8"], missed: [], wrong: [] }));
    renderPage("practice");
    expect(await screen.findByText("سؤال فلش؟")).toBeTruthy();

    drawArrow("d4", "d8");
    expect(await screen.findByTestId("arrow-list")).toBeTruthy();
    expect(screen.getByLabelText("حذف فلش d4→d8")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        puzzle_id: 1,
        answer: { moves: [{ from: "d4", to: "d8" }] },
        mode: "practice",
      }),
    );
    // Submission never ships the position answer, FEN overrides, or scores.
    const sent = (mockedApi.submitAttempt as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(sent.answer).not.toHaveProperty("fen");
    expect(sent.answer).not.toHaveProperty("moves Expected");
    expect(sent).not.toHaveProperty("score");
    expect(sent).not.toHaveProperty("result");
  });

  it("duplicate arrows normalize to one and direction matters", async () => {
    mockBoardRect();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال تکراری؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال تکراری؟")).toBeTruthy();

    drawArrow("d4", "d8");
    drawArrow("d4", "d8");
    expect(screen.getAllByLabelText("حذف فلش d4→d8").length).toBe(1);

    // Reverse direction is a different arrow.
    drawArrow("d8", "d4");
    expect(screen.getByLabelText("حذف فلش d8→d4")).toBeTruthy();
  });

  it("touch drag draws an arrow too", async () => {
    mockBoardRect();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال لمسی؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال لمسی؟")).toBeTruthy();
    drawArrow("d4", "h8", "touch");
    expect(screen.getByLabelText("حذف فلش d4→h8")).toBeTruthy();
  });

  it("arrows can be removed one by one and cleared", async () => {
    mockBoardRect();
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال حذف؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال حذف؟")).toBeTruthy();

    drawArrow("d4", "d8");
    drawArrow("d4", "h8");
    await user.click(screen.getByLabelText("حذف فلش d4→d8"));
    expect(screen.queryByLabelText("حذف فلش d4→d8")).toBeNull();
    expect(screen.getByLabelText("حذف فلش d4→h8")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "پاک کردن" }));
    expect(screen.queryByTestId("arrow-list")).toBeNull();
  });

  it("promotion arrows carry a per-arrow piece choice", async () => {
    mockBoardRect();
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال ترفیع؟", PROMO_FEN));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال ترفیع؟")).toBeTruthy();

    drawArrow("g7", "g8");
    expect(screen.getByLabelText("حذف فلش g7→g8")).toBeTruthy();
    // Default promotion is queen; switching to rook updates the payload.
    await user.click(screen.getByRole("button", { name: "R" }));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        answer: { moves: [{ from: "g7", to: "g8", promotion: "r" }] },
      }),
    );
  });

  it("feedback arrows are green/orange/red", async () => {
    mockBoardRect();
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "سؤال رنگ؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "partial", 2));
    renderPage("practice");
    expect(await screen.findByText("سؤال رنگ؟")).toBeTruthy();
    drawArrow("d4", "d8");
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    await screen.findByTestId("feedback");
    const strokes = Array.from(document.querySelectorAll("svg line")).map((l) =>
      l.getAttribute("stroke"),
    );
    expect(strokes).toContain("#16a34a");
    expect(strokes).toContain("#d97706");
    expect(strokes).toContain("#dc2626");
  });

  it("empty submission on a zero-target position is correct with +5", async () => {
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi.fn().mockResolvedValue(puzzle(9, "سؤال خالی؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue({ ...attempt(9, "correct", 5), detail: { correct: [], missed: [], wrong: [] } });
    renderPage("practice");
    expect(await screen.findByText("سؤال خالی؟")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({ answer: { moves: [] } }),
    );
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    expect(screen.getByText("۵ امتیاز")).toBeTruthy();
  });

  it("practice advances through second and third puzzles", async () => {
    mockBoardRect();
    const user = userEvent.setup();
    mockedApi.nextGiveCheckPracticePuzzle = vi
      .fn()
      .mockResolvedValueOnce(puzzle(1, "سؤال اول؟"))
      .mockResolvedValueOnce(puzzle(2, "سؤال دوم؟"))
      .mockResolvedValue(puzzle(3, "سؤال سوم؟"));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("سؤال اول؟")).toBeTruthy();
    drawArrow("d4", "d8");
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(await screen.findByText("آفرین! درست بود.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "معمای بعدی" }));
    expect(screen.getByText("سؤال دوم؟")).toBeTruthy();
    // Arrows reset per puzzle; draw again and continue to the third.
    drawArrow("d4", "h8");
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(2, "correct", 5));
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    await user.click(screen.getByRole("button", { name: "معمای بعدی" }));
    expect(screen.getByText("سؤال سوم؟")).toBeTruthy();
  });
});

describe("speed mode", () => {
  function mockActiveBoot(batch: Puzzle[], sessionId: string) {
    mockedApi.startGiveCheckSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "give-check",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareGiveCheckSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startGiveCheckSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "give-check",
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
    mockedApi.submitGiveCheckSpeedAnswer = vi.fn().mockImplementation(async (_sid: string, body: { puzzle_id: number }) => {
      n += 1;
      return {
        attempt: attempt(body.puzzle_id, "correct", 5, { correct: [], missed: [], wrong: [] }),
        feedback_key: "feedback.correct",
        detail: { correct: [], missed: [], wrong: [] },
        session: {
          session_id: sessionId,
          exercise_slug: "give-check",
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
    // Preparing state first: clock must not start before the buffer is ready.
    expect(await screen.findByText("در حال آماده‌سازی...")).toBeTruthy();
    expect(await screen.findByText("سؤال 1؟")).toBeTruthy();
    expect(mockedApi.prepareGiveCheckSpeedPuzzles).toHaveBeenCalledWith("s1", { count: 20 });
    expect(mockedApi.startGiveCheckSpeedClock).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("زمان باقی‌مانده")).toBeTruthy();
    // Buffer internals are never shown.
    expect(screen.queryByText("20")).toBeNull();
  });

  it("three consecutive speed puzzles auto-advance with a double-submit lock", async () => {
    vi.useFakeTimers();
    try {
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `پی ${i + 1}؟`));
      mockActiveBoot(batch, "chain1");
      mockSubmitOk("chain1");

      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("پی 1؟")).toBeTruthy();

      for (let i = 1; i <= 3; i++) {
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
        await act(async () => {});
        // Double-submit lock: one call per puzzle despite two clicks.
        expect(mockedApi.submitGiveCheckSpeedAnswer).toHaveBeenCalledTimes(i);
        expect(mockedApi.submitGiveCheckSpeedAnswer).toHaveBeenLastCalledWith(
          "chain1",
          expect.objectContaining({ puzzle_id: i }),
        );
        // No manual next button anywhere in Speed Mode.
        expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();

        await act(async () => {
          await vi.advanceTimersByTimeAsync(500);
        });
        // Auto-advanced; timer still visible.
        expect(screen.getByText(`پی ${i + 1}؟`)).toBeTruthy();
      }
    } finally {
      vi.useRealTimers();
    }
  });

  it("speed arrows draw during the run and clear on advance", async () => {
    vi.useFakeTimers();
    try {
      mockBoardRect();
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `لمس ${i + 1}؟`));
      mockActiveBoot(batch, "chain2");
      mockSubmitOk("chain2");

      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("لمس 1؟")).toBeTruthy();
      drawArrow("d4", "d8");
      expect(screen.getByLabelText("حذف فلش d4→d8")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "بررسی جواب" }));
      await act(async () => {});
      expect(mockedApi.submitGiveCheckSpeedAnswer).toHaveBeenCalledWith(
        "chain2",
        expect.objectContaining({ answer: { moves: [{ from: "d4", to: "d8" }] } }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
      expect(screen.getByText("لمس 2؟")).toBeTruthy();
      expect(screen.queryByLabelText("حذف فلش d4→d8")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
