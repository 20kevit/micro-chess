import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BalanceScalePage } from "../../pages/BalanceScalePage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import { fa } from "../../i18n/fa";
import {
  FULL_FLASH_MS,
  SPEED_FEEDBACK_MS,
  answerForPieces,
  leftOf,
} from "./BalanceScalePlay";
import {
  ANGLE_SOFTNESS,
  MAX_ANGLE_DEG,
  MAX_PAN_PIECES,
  layoutPyramid,
  pieceValue,
  scaleAngle,
  sortHeavyFirst,
  totalOf,
} from "./BalanceScaleView";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
vi.mock("../../lib/sound", () => ({ playError: vi.fn(), playSuccess: vi.fn() }));
import { api } from "../../api/client";
import { playSuccess } from "../../lib/sound";

const mockedApi = vi.mocked(api, true);
const mockedPlaySuccess = vi.mocked(playSuccess);

function puzzle(id: number, left: string[]): Puzzle {
  return {
    id,
    exercise_slug: "balance-scale",
    fen: null,
    position_json: { left },
    hint_json: { hints: [] },
    prompt_fa: "prompt",
    explanation: "",
    initial_rating: 900,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number, score: number): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "balance-scale",
    mode: "practice",
    result: "correct",
    score,
    feedback_key: "feedback.correct",
    rating_delta: null,
    detail: { correct: [], missed: [], wrong: [] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/balance-scale?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/balance-scale" element={<BalanceScalePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function speedSession(id: string, status: "preparing" | "active" | "finished" | "expired", remainingMs = 60000) {
  return {
    session_id: id,
    exercise_slug: "balance-scale",
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

/** Flush pending promises/timers until the scale appears (fake timers on). */
async function flushBoot(maxRounds = 16) {
  for (let i = 0; i < maxRounds; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    if (screen.queryByTestId("balance-scale")) return;
  }
}

beforeEach(() => {
  for (const key of Object.keys(mockedApi)) {
    delete (mockedApi as Record<string, unknown>)[key];
  }
  mockedPlaySuccess.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("pure helpers", () => {
  it("values and totals match the standard material table", () => {
    expect(pieceValue("P")).toBe(1);
    expect(pieceValue("N")).toBe(3);
    expect(pieceValue("B")).toBe(3);
    expect(pieceValue("R")).toBe(5);
    expect(pieceValue("Q")).toBe(9);
    expect(totalOf(["Q", "R", "P"])).toBe(15);
    expect(totalOf([])).toBe(0);
  });

  it("sorts heavy pieces first, stable for equal values", () => {
    expect(sortHeavyFirst([{ kind: "P" }, { kind: "Q" }, { kind: "R" }]).map((p) => p.kind)).toEqual([
      "Q",
      "R",
      "P",
    ]);
    // Equal values keep insertion order.
    expect(sortHeavyFirst([{ kind: "N" }, { kind: "B" }]).map((p) => p.kind)).toEqual(["N", "B"]);
  });

  it("lays out the 1-2-3-4 pyramid with heavy pieces at the bottom", () => {
    const items = ["P", "P", "N", "B", "R", "Q"].map((kind, uid) => ({ uid, kind }));
    const rows = layoutPyramid(items);
    // Bottom-up fill: 4 heaviest at the bottom, remaining 2 above.
    expect(rows.map((r) => r.length)).toEqual([0, 0, 2, 4]);
    expect(rows[3].map((p) => p.kind)).toEqual(["Q", "R", "N", "B"]);
    expect(rows[2].map((p) => p.kind)).toEqual(["P", "P"]);
  });

  it("pyramid row capacities are 1/2/3/4 for a full pan", () => {
    const items = Array.from({ length: 10 }, (_, uid) => ({ uid, kind: "P" }));
    expect(layoutPyramid(items).map((r) => r.length)).toEqual([1, 2, 3, 4]);
  });

  it("scale angle is zero when balanced, signed, and bounded", () => {
    expect(scaleAngle(0)).toBe(0);
    expect(scaleAngle(-5)).toBeLessThan(0);
    expect(scaleAngle(5)).toBeGreaterThan(0);
    expect(Math.abs(scaleAngle(1000))).toBeLessThanOrEqual(MAX_ANGLE_DEG);
    expect(Math.abs(scaleAngle(-1000))).toBeLessThanOrEqual(MAX_ANGLE_DEG);
    // Smooth nonlinear mapping: half tilt at |diff| = softness.
    expect(scaleAngle(ANGLE_SOFTNESS)).toBeCloseTo(MAX_ANGLE_DEG / 2, 5);
    // Monotonic in magnitude.
    expect(Math.abs(scaleAngle(20))).toBeGreaterThan(Math.abs(scaleAngle(5)));
  });

  it("leftOf reads public task data and answerForPieces ships pieces only", () => {
    expect(leftOf(puzzle(1, ["q", "r"]))).toEqual(["Q", "R"]);
    expect(answerForPieces(["Q", "P"])).toEqual({ pieces: ["Q", "P"] });
  });
});

describe("practice mode", () => {
  it("renders the scale, both pans, the pyramid, and the inventory", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBalancePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, ["r", "b", "p", "p"]));
      renderPage("practice");
      await flushBoot();
      expect(screen.getByTestId("balance-scale")).toBeTruthy();
      expect(screen.getByTestId("left-pan")).toBeTruthy();
      expect(screen.getByTestId("right-pan")).toBeTruthy();
      expect(screen.getByTestId("inventory")).toBeTruthy();
      for (const kind of ["P", "N", "B", "R", "Q"]) {
        expect(screen.getByTestId(`inventory-${kind}`)).toBeTruthy();
      }
      // Left pan shows 4 black pieces in pyramid rows.
      expect(screen.getAllByTestId("black-piece")).toHaveLength(4);
      expect(screen.getByTestId("left-pyramid-row-0")).toBeTruthy();
      expect(screen.getByTestId("left-pyramid-row-3")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("adding inventory pieces updates totals and tilts the beam", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBalancePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, ["r", "b", "p", "p"]));
      renderPage("practice");
      await flushBoot();
      const beam = screen.getByTestId("scale-beam");
      // Right pan starts empty (0 < 10): the beam already leans left.
      const initial = Number(beam.getAttribute("data-angle"));
      expect(initial).toBeLessThan(0);
      fireEvent.click(screen.getByTestId("inventory-R"));
      expect(screen.getAllByTestId("white-piece")).toHaveLength(1);
      // Right is still lighter (5 < 10) but closer to balance.
      const tilted = Number(screen.getByTestId("scale-beam").getAttribute("data-angle"));
      expect(tilted).toBeLessThan(0);
      expect(tilted).toBeGreaterThan(initial);
    } finally {
      vi.useRealTimers();
    }
  });

  it("clicking a white piece removes it; black pieces cannot be removed", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBalancePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, ["r", "b", "p", "p"]));
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByTestId("inventory-R"));
      expect(screen.getAllByTestId("white-piece")).toHaveLength(1);
      // Left pan pieces are not buttons.
      expect(screen.getByTestId("left-pan").querySelector("button")).toBeNull();
      fireEvent.click(screen.getByTestId("white-piece"));
      expect(screen.queryAllByTestId("white-piece")).toHaveLength(0);
      expect(screen.getAllByTestId("black-piece")).toHaveLength(4);
    } finally {
      vi.useRealTimers();
    }
  });

  it("enforces the 10-piece capacity with feedback but no penalty", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBalancePracticePuzzle = vi
        .fn()
        .mockResolvedValue(puzzle(1, ["q", "q", "r", "b", "p", "p"]));
      mockedApi.submitAttempt = vi.fn();
      renderPage("practice");
      await flushBoot();
      for (let i = 0; i < MAX_PAN_PIECES; i++) {
        fireEvent.click(screen.getByTestId("inventory-P"));
      }
      expect(screen.getAllByTestId("white-piece")).toHaveLength(10);
      fireEvent.click(screen.getByTestId("inventory-P"));
      expect(screen.getAllByTestId("white-piece")).toHaveLength(10);
      expect(screen.getByText(fa["balance.panFull"])).toBeTruthy();
      expect(mockedApi.submitAttempt).not.toHaveBeenCalled();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(FULL_FLASH_MS + 60);
      });
      expect(screen.queryByText(fa["balance.panFull"])).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("auto-submits on exact balance, celebrates, scores, and waits for next", async () => {
    vi.useFakeTimers();
    try {
      const first = puzzle(1, ["r", "b"]); // target 8
      const second = puzzle(2, ["q", "p", "p", "p"]);
      mockedApi.nextBalancePracticePuzzle = vi
        .fn()
        .mockResolvedValueOnce(first)
        .mockResolvedValue(second);
      mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, 10));
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByTestId("inventory-R"));
      fireEvent.click(screen.getByTestId("inventory-B"));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      // Auto-submitted with the exact white pieces, no score smuggling.
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
      expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
        expect.objectContaining({ puzzle_id: 1, answer: { pieces: ["R", "B"] }, mode: "practice" }),
      );
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      // Balanced state is perfectly horizontal with a success state + score.
      expect(screen.getByTestId("scale-beam").getAttribute("data-angle")).toBe("0.00");
      expect(screen.getByTestId("balanced-message")).toBeTruthy();
      expect(screen.getByTestId("next-question")).toBeTruthy();
      // Practice does NOT auto-advance: still exactly one submission.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(mockedApi.submitAttempt).toHaveBeenCalledTimes(1);
      // Explicit next question resets the pan.
      fireEvent.click(screen.getByTestId("next-question"));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(screen.queryAllByTestId("white-piece")).toHaveLength(0);
      expect(screen.queryByTestId("next-question")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("under/over target never submits", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.nextBalancePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, ["r", "b"]));
      mockedApi.submitAttempt = vi.fn();
      renderPage("practice");
      await flushBoot();
      fireEvent.click(screen.getByTestId("inventory-R")); // 5 < 8
      await act(async () => {});
      fireEvent.click(screen.getByTestId("inventory-Q")); // 14 > 8
      await act(async () => {});
      expect(mockedApi.submitAttempt).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed mode", () => {
  it("boots a session, auto-submits on balance, and auto-advances", async () => {
    vi.useFakeTimers();
    try {
      const buffer = Array.from({ length: 20 }, (_, i) => puzzle(300 + i, ["r", "b"]));
      mockedApi.startBalanceSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareBalanceSpeedPuzzles = vi.fn().mockResolvedValue(buffer);
      mockedApi.startBalanceSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active"));
      mockedApi.finishBalanceSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.submitBalanceSpeedAnswer = vi.fn().mockResolvedValue({
        attempt: { ...attempt(300, 10), mode: "practice" },
        feedback_key: "feedback.correct",
        detail: {},
        session: { ...speedSession("s1", "active"), attempted: 1, correct: 1, score: 10 },
      });
      renderPage("speed");
      await flushBoot();
      expect(screen.getByTestId("timer")).toBeTruthy();
      // Speed shows no next-question button.
      expect(screen.queryByTestId("next-question")).toBeNull();
      fireEvent.click(screen.getByTestId("inventory-R"));
      fireEvent.click(screen.getByTestId("inventory-B"));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(mockedApi.submitBalanceSpeedAnswer).toHaveBeenCalledTimes(1);
      expect(mockedPlaySuccess).toHaveBeenCalledTimes(1);
      // Auto-advances without a manual button.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(SPEED_FEEDBACK_MS + 60);
      });
      expect(screen.queryAllByTestId("white-piece")).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("finishes with the server-built report when the clock expires", async () => {
    vi.useFakeTimers();
    try {
      mockedApi.startBalanceSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "preparing"));
      mockedApi.prepareBalanceSpeedPuzzles = vi
        .fn()
        .mockResolvedValue(Array.from({ length: 20 }, (_, i) => puzzle(200 + i, ["r", "b"])));
      mockedApi.startBalanceSpeedClock = vi.fn().mockResolvedValue(speedSession("s1", "active", 1000));
      mockedApi.finishBalanceSpeedSession = vi.fn().mockResolvedValue(speedSession("s1", "finished", 0));
      mockedApi.getBalanceSpeedReport = vi.fn().mockResolvedValue({
        session: { ...speedSession("s1", "finished", 0), attempted: 0, correct: 0, wrong: 0, score: 0 },
        entries: [],
      });
      renderPage("speed");
      await flushBoot();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(mockedApi.finishBalanceSpeedSession).toHaveBeenCalled();
      expect(screen.getByText(fa["speed.result"])).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("catalog and i18n", () => {
  it("exposes practice and speed entry modes", () => {
    const meta = getExerciseMeta("balance-scale");
    expect(meta?.status).toBe("active");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("defines every user-visible balance string", () => {
    for (const key of [
      "balance.intro",
      "balance.blackPan",
      "balance.whitePan",
      "balance.blackTotal",
      "balance.whiteTotal",
      "balance.inventory",
      "balance.balanced",
      "balance.howto",
      "balance.panFull",
      "balance.score",
      "balance.values",
    ] as const) {
      expect(fa[key], key).toBeTruthy();
    }
  });
});
