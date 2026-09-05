import { describe, expect, it } from "vitest";
import {
  GAME_BOARD_MAX,
  fitSquareSize,
  orientationOf,
} from "./PieceGameLayout";

describe("responsive layout logic", () => {
  it("wide screens play side-by-side, tall screens stack", () => {
    expect(orientationOf(844, 390)).toBe("landscape");
    expect(orientationOf(667, 375)).toBe("landscape");
    expect(orientationOf(1280, 720)).toBe("landscape");
    expect(orientationOf(360, 800)).toBe("portrait");
    expect(orientationOf(390, 844)).toBe("portrait");
    expect(orientationOf(1024, 768)).toBe("landscape");
    // Square viewport stacks (no horizontal gain from a side column).
    expect(orientationOf(500, 500)).toBe("portrait");
  });

  it("board fits the smaller area side, capped for huge screens", () => {
    expect(fitSquareSize(336, 554)).toBe(336);
    expect(fitSquareSize(580, 330)).toBe(330);
    expect(fitSquareSize(2000, 2000)).toBe(GAME_BOARD_MAX);
    expect(fitSquareSize(100, 100, 80)).toBe(80);
    expect(fitSquareSize(0, 500)).toBe(0);
    expect(fitSquareSize(-10, 500)).toBe(0);
    expect(fitSquareSize(Number.NaN, 500)).toBe(0);
  });

  it("every target viewport fits board + chrome budgets", () => {
    // Chrome budgets: portrait top/question/timer/action+gaps; landscape
    // topbar + side column. Board = min(area) via the same fit function.
    const cases: Array<[number, number, number]> = [
      // [w, h, min acceptable board px]
      [360, 800, 300],
      [390, 844, 300],
      [412, 915, 300],
      [667, 375, 180],
      [844, 390, 200],
      [1024, 768, 400],
      [1280, 720, 400],
      [1366, 768, 400],
    ];
    for (const [w, h, minBoard] of cases) {
      const landscape = orientationOf(w, h) === "landscape";
      // Conservative chrome estimates (generous vs the compact components).
      const board = landscape
        ? fitSquareSize(w - 264, h - 60)
        : fitSquareSize(w - 24, h - 300);
      expect(board, `${w}x${h}`).toBeGreaterThanOrEqual(minBoard);
    }
  });
});
