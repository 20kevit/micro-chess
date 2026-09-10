import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PathfindingObstaclesPage } from "../../pages/PathfindingObstaclesPage";
import { getExerciseMeta } from "../../exercises/catalog";
import type { AttemptResponse, Puzzle } from "../../api/types";
import {
  ILLEGAL_FLASH_MS,
  PRACTICE_ANIM_MS,
  SPEED_ANIM_MS,
  SPEED_FEEDBACK_MS,
  answerForPath,
  obstaclePosOf,
  squareCenter,
} from "./PathfindingObstaclesPlay";

vi.mock("../../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../api/client")>();
  return { ...orig, api: {} };
});
vi.mock("../../lib/sound", () => ({ playError: vi.fn(), playSuccess: vi.fn() }));
import { api } from "../../api/client";
import { playError, playSuccess } from "../../lib/sound";

const mockedApi = vi.mocked(api, true);
const mockedPlayError = vi.mocked(playError);
const mockedPlaySuccess = vi.mocked(playSuccess);

const ROOK_A1_FEN = "7n/8/8/8/8/8/8/R7 w - - 0 1";
const KNIGHT_B1_FEN = "8/8/8/8/8/8/8/1N6 w - - 0 1";
// Rook a1 blocked by a black pawn on a4 (capturable when undefended).
const ROOK_A1_PAWN_A4_FEN = "8/8/8/8/p7/8/8/R7 w - - 0 1";
const ROOK_A4_FEN = "8/8/8/8/R7/8/8/8 w - - 0 1";

function puzzle(
  id: number,
  prompt: string,
  fen = ROOK_A1_FEN,
  from = "a1",
  target = "a8",
  piece = "rook",
  enemies: { square: string; kind: string }[] = [{ square: "h8", kind: "knight" }],
): Puzzle {
  return {
    id,
    exercise_slug: "pathfinding-obstacles",
    fen,
    position_json: { from, target, piece, enemies },
    hint_json: { hints: [] },
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
  detail: AttemptResponse["detail"] = { correct: ["a1", "a8"], missed: [], wrong: [] },
): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "pathfinding-obstacles",
    mode: "practice",
    result,
    score,
    feedback_key: result === "correct" ? "feedback.correct" : "feedback.wrong",
    rating_delta: null,
    detail,
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage(mode: string) {
  return render(
    <MemoryRouter initialEntries={[`/exercises/pathfinding-obstacles?mode=${mode}`]}>
      <Routes>
        <Route path="/exercises/pathfinding-obstacles" element={<PathfindingObstaclesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

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

function tap(square: string, pointerType = "mouse") {
  const cell = screen.getByRole("gridcell", { name: square });
  const at = squareXY(square);
  fireEvent.pointerDown(cell, { pointerType, button: 0, pointerId: 1, ...at });
  fireEvent.pointerUp(cell, { pointerType, button: 0, pointerId: 1, ...at });
}

function drag(from: string, to: string, pointerType = "mouse") {
  const origin = screen.getByRole("gridcell", { name: from });
  const start = squareXY(from);
  const end = squareXY(to);
  fireEvent.pointerDown(origin, { pointerType, button: 0, pointerId: 1, ...start });
  fireEvent.pointerMove(origin, { pointerType, button: 0, pointerId: 1, ...end });
  fireEvent.pointerUp(origin, { pointerType, button: 0, pointerId: 1, ...end });
}

// Step oracle mock: moves the piece inside the FEN like the real backend,
// so consecutive steps see the updated position.
function moveFen(fen: string, from: string, to: string): string {
  const [placement, ...rest] = fen.split(" ");
  const rows = placement.split("/");
  const get = (sq: string): string | null => {
    const f = sq.charCodeAt(0) - "a".charCodeAt(0);
    const r = 8 - Number(sq.slice(1));
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) file += Number(ch);
      else {
        if (file === f) return ch;
        file += 1;
      }
    }
    return null;
  };
  const set = (sq: string, value: string | null) => {
    const f = sq.charCodeAt(0) - "a".charCodeAt(0);
    const r = 8 - Number(sq.slice(1));
    const cells: (string | null)[] = [];
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) for (let i = 0; i < Number(ch); i++) cells.push(null);
      else cells.push(ch);
    }
    cells[f] = value;
    let row = "";
    let empty = 0;
    for (const c of cells) {
      if (c === null) empty += 1;
      else {
        if (empty) {
          row += String(empty);
          empty = 0;
        }
        row += c;
      }
    }
    if (empty) row += String(empty);
    rows[r] = row;
  };
  const piece = get(from);
  if (!piece) return fen;
  set(from, null);
  set(to, piece);
  return [rows.join("/"), ...rest].join(" ");
}

function mockStepOk(target: string) {
  mockedApi.validateObstacleStep = vi.fn().mockImplementation(
    async (body: { from: string; to: string; fen: string }) => ({
      ok: true,
      fen: moveFen(body.fen, body.from, body.to),
      selected_at: body.to,
      reached: body.to === target,
      captured: null,
      message_key: "",
    }),
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useRealTimers();
  mockedApi.finishObstacleSpeedSession = vi.fn().mockResolvedValue({
    session_id: "none",
    exercise_slug: "pathfinding-obstacles",
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

describe("pure helpers", () => {
  it("answerForPath ships path + illegal count only", () => {
    expect(answerForPath(["a1", "a8"], 2)).toEqual({ path: ["a1", "a8"], illegal_attempts: 2 });
    expect(answerForPath(["a1"], -5)).toEqual({ path: ["a1"], illegal_attempts: 0 });
  });

  it("obstaclePosOf reads public task data incl. enemies", () => {
    expect(obstaclePosOf(puzzle(1, "x"))).toEqual({
      from: "a1",
      target: "a8",
      piece: "rook",
      enemies: [{ square: "h8", kind: "knight" }],
    });
  });

  it("squareCenter maps a1/h8 to board units", () => {
    expect(squareCenter("a1")).toEqual({ x: 0.5, y: 7.5 });
    expect(squareCenter("h8")).toEqual({ x: 7.5, y: 0.5 });
  });

  it("speed animation is faster than practice", () => {
    expect(SPEED_ANIM_MS).toBeLessThan(PRACTICE_ANIM_MS);
  });
});

describe("catalog direct entry", () => {
  it("pathfinding-obstacles exposes practice and speed entries", () => {
    const meta = getExerciseMeta("pathfinding-obstacles");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/pathfinding-obstacles");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("mode entries point at distinct mode URLs", () => {
    const meta = getExerciseMeta("pathfinding-obstacles");
    const urls = new Set((meta?.modes ?? []).map((m) => `${meta?.route}${m.params}`));
    expect(urls).toEqual(
      new Set(["/exercises/pathfinding-obstacles?mode=practice", "/exercises/pathfinding-obstacles?mode=speed"]),
    );
  });
});

describe("practice movement", () => {
  it("?mode=practice enters practice directly with star + selected piece", async () => {
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "به ستاره برسان؟"));
    renderPage("practice");
    expect(await screen.findByText("به ستاره برسان؟")).toBeTruthy();
    // Star marker rendered (gold star path), piece starts selected.
    expect(document.querySelector('path[fill="#fbbf24"]')).not.toBeNull();
    expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("status-line").textContent).toContain("حرکت‌ها");
  });

  it("click destination moves the piece and keeps it selected", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "کلیک؟"));
    mockStepOk("a8");
    renderPage("practice");
    expect(await screen.findByText("کلیک؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("a4");
      await act(async () => {});
      expect(mockedApi.validateObstacleStep).toHaveBeenCalledWith(
        expect.objectContaining({ from: "a1", to: "a4" }),
      );
      // Glide animation runs, then commits.
      expect(screen.getByTestId("move-anim")).toBeTruthy();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      // Piece arrived and REMAINS selected for the next click.
      expect(screen.getByRole("gridcell", { name: "a4" }).getAttribute("aria-pressed")).toBe("true");
      expect(screen.getByTestId("status-line").textContent).toContain("۱");
    } finally {
      vi.useRealTimers();
    }
  });

  it("drag moves the piece too (touch)", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi
      .fn()
      .mockResolvedValue(puzzle(1, "درگ؟", KNIGHT_B1_FEN, "b1", "c3", "knight"));
    mockStepOk("c3");
    renderPage("practice");
    expect(await screen.findByText("درگ؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      drag("b1", "c3", "touch");
      await act(async () => {});
      expect(mockedApi.validateObstacleStep).toHaveBeenCalledWith(
        expect.objectContaining({ from: "b1", to: "c3" }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      expect(screen.getByRole("gridcell", { name: "c3" }).getAttribute("aria-pressed")).toBe("true");
    } finally {
      vi.useRealTimers();
    }
  });

  it("repeated clicks walk step by step without reselecting", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "قدم؟"));
    mockStepOk("a8");
    renderPage("practice");
    expect(await screen.findByText("قدم؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("a4");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      tap("a6");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      expect(mockedApi.validateObstacleStep).toHaveBeenCalledTimes(2);
      expect(screen.getByRole("gridcell", { name: "a6" }).getAttribute("aria-pressed")).toBe("true");
      expect(screen.getByTestId("status-line").textContent).toContain("۲");
    } finally {
      vi.useRealTimers();
    }
  });

  it("tapping the selected piece again keeps it selected", async () => {
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "خودش؟"));
    renderPage("practice");
    expect(await screen.findByText("خودش؟")).toBeTruthy();
    tap("a1");
    await act(async () => {});
    expect(mockedApi.validateObstacleStep).not.toHaveBeenCalled();
    expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("illegal destination buzzes, flashes red, stays, counts -3 state", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "خطا؟"));
    mockedApi.validateObstacleStep = vi.fn().mockResolvedValue({
      ok: false,
      fen: ROOK_A1_FEN,
      selected_at: "a1",
      reached: false,
      captured: null,
      message_key: "pathfinding.invalid",
    });
    renderPage("practice");
    expect(await screen.findByText("خطا؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("b2");
      await act(async () => {});
      expect(mockedPlayError).toHaveBeenCalledTimes(1);
      // Piece stays, stays selected, red destination highlight.
      expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("true");
      const bad = screen.getByRole("gridcell", { name: "b2" });
      expect(bad.className).toContain("outline-red-500");
      expect(screen.getByTestId("status-line").textContent).toContain("۱");
      // Flash is temporary.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(ILLEGAL_FLASH_MS + 60);
      });
      expect(screen.getByRole("gridcell", { name: "b2" }).className).not.toContain("outline-red-500");
    } finally {
      vi.useRealTimers();
    }
  });

  it("reaching the star submits path + illegal count, never scores", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "پایان؟"));
    mockStepOk("a8");
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("پایان؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("a8");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      await act(async () => {});
      expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
        expect.objectContaining({
          puzzle_id: 1,
          answer: { path: ["a1", "a8"], illegal_attempts: 0 },
          mode: "practice",
        }),
      );
      const sent = (mockedApi.submitAttempt as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(sent.answer).not.toHaveProperty("score");
      expect(sent.answer).not.toHaveProperty("optimal_moves");
      expect(sent.answer).not.toHaveProperty("optimalMoves");
      expect(sent).not.toHaveProperty("score");
      expect(mockedPlaySuccess).toHaveBeenCalled();
      expect(screen.getByTestId("arrived")).toBeTruthy();
      expect(screen.getByText("۵ امتیاز")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("practice advances to the prefetched next puzzle", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi
      .fn()
      .mockResolvedValueOnce(puzzle(1, "اول؟"))
      .mockResolvedValueOnce(puzzle(2, "دوم؟"))
      .mockResolvedValue(puzzle(3, "سوم؟"));
    mockStepOk("a8");
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 5));
    renderPage("practice");
    expect(await screen.findByText("اول؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("a8");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      await act(async () => {});
      expect(screen.getByTestId("arrived")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "معمای بعدی" }));
      expect(screen.getByText("دوم؟")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("speed mode", () => {
  function mockActiveBoot(batch: Puzzle[], sessionId: string) {
    mockedApi.startObstacleSpeedSession = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "pathfinding-obstacles",
      status: "preparing",
      duration_s: 60,
      started_at: new Date().toISOString(),
      expires_at: null,
      remaining_ms: 60000,
      buffered: 0,
    });
    mockedApi.prepareObstacleSpeedPuzzles = vi.fn().mockResolvedValue(batch);
    mockedApi.startObstacleSpeedClock = vi.fn().mockResolvedValue({
      session_id: sessionId,
      exercise_slug: "pathfinding-obstacles",
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
    mockedApi.submitObstacleSpeedAnswer = vi.fn().mockImplementation(
      async (_sid: string, body: { puzzle_id: number }) => {
        n += 1;
        return {
          attempt: attempt(body.puzzle_id, "correct", 5, { correct: [], missed: [], wrong: [] }),
          feedback_key: "feedback.correct",
          detail: { correct: [], missed: [], wrong: [] },
          session: {
            session_id: sessionId,
            exercise_slug: "pathfinding-obstacles",
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
      },
    );
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
    expect(mockedApi.prepareObstacleSpeedPuzzles).toHaveBeenCalledWith("s1", { count: 20 });
    expect(mockedApi.startObstacleSpeedClock).toHaveBeenCalledWith("s1");
    expect(await screen.findByText("زمان باقی‌مانده")).toBeTruthy();
    expect(screen.queryByText("20")).toBeNull();
  });

  it("speed reaches the star and auto-advances with no manual next", async () => {
    vi.useFakeTimers();
    try {
      mockBoardRect();
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `تند ${i + 1}؟`));
      mockActiveBoot(batch, "chain1");
      mockSubmitOk("chain1");
      mockStepOk("a8");
      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("تند 1؟")).toBeTruthy();

      tap("a8");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(SPEED_ANIM_MS + 60);
      });
      await act(async () => {});
      expect(mockedApi.submitObstacleSpeedAnswer).toHaveBeenCalledWith(
        "chain1",
        expect.objectContaining({
          puzzle_id: 1,
          answer: { path: ["a1", "a8"], illegal_attempts: 0 },
        }),
      );
      expect(screen.queryByRole("button", { name: "معمای بعدی" })).toBeNull();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(SPEED_FEEDBACK_MS + 60);
      });
      expect(screen.getByText("تند 2؟")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("speed illegal move buzzes and keeps the puzzle going", async () => {
    vi.useFakeTimers();
    try {
      mockBoardRect();
      const batch = Array.from({ length: 20 }, (_, i) => puzzle(i + 1, `خطای تند ${i + 1}؟`));
      mockActiveBoot(batch, "chain2");
      mockSubmitOk("chain2");
      mockedApi.validateObstacleStep = vi.fn().mockResolvedValue({
        ok: false,
        fen: ROOK_A1_FEN,
        selected_at: "a1",
        reached: false,
        captured: null,
        message_key: "pathfinding.invalid",
      });
      renderPage("speed");
      await flushBoot();
      expect(screen.getByText("خطای تند 1؟")).toBeTruthy();

      tap("b2");
      await act(async () => {});
      expect(mockedPlayError).toHaveBeenCalled();
      expect(mockedApi.submitObstacleSpeedAnswer).not.toHaveBeenCalled();
      expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("true");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("obstacle specifics", () => {
  it("renders the star target together with enemy pieces", async () => {
    mockedApi.nextObstaclePracticePuzzle = vi.fn().mockResolvedValue(puzzle(1, "مانع؟"));
    renderPage("practice");
    expect(await screen.findByText("مانع؟")).toBeTruthy();
    // Star marker rendered (gold star path).
    expect(document.querySelector('path[fill="#fbbf24"]')).not.toBeNull();
    // Enemy knight on h8 renders a piece (SVG asset image) inside its square.
    const enemy = screen.getByRole("gridcell", { name: "h8" });
    expect(enemy.querySelector("img")).not.toBeNull();
    // White rook still starts selected.
    expect(screen.getByRole("gridcell", { name: "a1" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("capture removes the enemy and the next step sees the new position", async () => {
    mockBoardRect();
    mockedApi.nextObstaclePracticePuzzle = vi
      .fn()
      .mockResolvedValue(
        puzzle(1, "بزن؟", ROOK_A1_PAWN_A4_FEN, "a1", "a8", "rook", [
          { square: "a4", kind: "pawn" },
        ]),
      );
    // Capture oracle: first step takes the pawn, second step walks to the star.
    mockedApi.validateObstacleStep = vi
      .fn()
      .mockImplementationOnce(async () => ({
        ok: true,
        fen: ROOK_A4_FEN,
        selected_at: "a4",
        reached: false,
        captured: "a4",
        message_key: "",
      }))
      .mockImplementationOnce(async (body: { to: string; fen: string }) => ({
        ok: true,
        fen: moveFen(body.fen, "a4", body.to),
        selected_at: body.to,
        reached: body.to === "a8",
        captured: null,
        message_key: "",
      }));
    mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1, "correct", 10));
    renderPage("practice");
    expect(await screen.findByText("بزن؟")).toBeTruthy();
    vi.useFakeTimers();
    try {
      tap("a4");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      // Piece captured, stays selected, illegal counter untouched.
      expect(screen.getByRole("gridcell", { name: "a4" }).getAttribute("aria-pressed")).toBe("true");
      expect(screen.getByTestId("status-line").textContent).toContain("۱");
      tap("a8");
      await act(async () => {});
      await act(async () => {
        await vi.advanceTimersByTimeAsync(PRACTICE_ANIM_MS + 60);
      });
      await act(async () => {});
      // The second step saw the post-capture board (pawn gone).
      const second = (mockedApi.validateObstacleStep as ReturnType<typeof vi.fn>).mock.calls[1][0];
      expect(second.fen).toBe(ROOK_A4_FEN);
      expect(second.fen).not.toContain("p");
      expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
        expect.objectContaining({
          puzzle_id: 1,
          answer: { path: ["a1", "a4", "a8"], illegal_attempts: 0 },
          mode: "practice",
        }),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("obstacle catalog strings are Persian", async () => {
    const { t } = await import("../../i18n");
    expect(t("exercises.pathfinding-obstacles.title")).toBe("مسیریابی با مانع");
  });
});
