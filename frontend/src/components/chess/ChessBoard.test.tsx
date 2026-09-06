import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ARROW_GEOMETRY,
  arrowKey,
  arrowToUci,
  ChessBoard,
  computeArrowGeometry,
  normalizeArrows,
  uciToArrow,
} from "./ChessBoard";

describe("arrow helpers", () => {
  it("arrowKey is direction-sensitive and case-insensitive", () => {
    expect(arrowKey({ from: "e2", to: "e4" })).toBe("e2e4");
    expect(arrowKey({ from: "E2", to: "E4" })).toBe("e2e4");
    expect(arrowKey({ from: "e2", to: "e4" })).not.toBe(arrowKey({ from: "e4", to: "e2" }));
  });

  it("normalizeArrows dedupes, keeps direction, drops zero-length", () => {
    const out = normalizeArrows([
      { from: "e2", to: "e4" },
      { from: "e2", to: "e4" },
      { from: "e4", to: "e2" },
      { from: "d4", to: "d4" },
    ]);
    expect(out).toEqual([
      { from: "e2", to: "e4" },
      { from: "e4", to: "e2" },
    ]);
  });

  it("uciToArrow splits UCI incl. promotions, rejects malformed", () => {
    expect(uciToArrow("e2e4")).toEqual({ from: "e2", to: "e4" });
    expect(uciToArrow("G7G8Q")).toEqual({ from: "g7", to: "g8", promotion: "q" });
    expect(uciToArrow("e2e9")).toBeNull();
    expect(uciToArrow("o-o")).toBeNull();
    expect(uciToArrow("")).toBeNull();
  });

  it("arrowToUci joins parts, keeping only valid promotion letters", () => {
    expect(arrowToUci("e2", "e4")).toBe("e2e4");
    expect(arrowToUci("g7", "g8", "Q")).toBe("g7g8q");
    expect(arrowToUci("e2", "e4", "k")).toBe("e2e4");
    expect(arrowToUci("e2", "e4", "qr")).toBe("e2e4");
  });
});

describe("multi-arrow rendering", () => {
  it("renders every arrow as a shaft plus an independent head", () => {
    render(
      <ChessBoard
        pieces={{ e2: "P", e7: "p" }}
        arrowsEnabled
        arrows={[
          { from: "e2", to: "e4" },
          { from: "e7", to: "e5" },
        ]}
      />,
    );
    const svg = document.querySelector("svg");
    expect(svg?.getAttribute("viewBox")).toBe("0 0 8 8");
    expect(svg?.querySelectorAll("line").length).toBe(2);
    expect(svg?.querySelectorAll("polygon").length).toBe(2);
    const lines = svg?.querySelectorAll("line") ?? [];
    // e-file center is x=4.5 in board units regardless of pixel size, so
    // arrows stay aligned when the board resizes (SVG scales the viewBox).
    expect(lines[0].getAttribute("x1")).toBe("4.5");
    expect(lines[0].getAttribute("y1")).toBe("6.5");
    // Core invariant: the shaft ends at the arrowhead BASE (y≈4.95), NOT
    // at the destination center (y=4.5).
    const y2 = Number(lines[0].getAttribute("y2"));
    expect(y2).toBeGreaterThan(4.5);
    expect(y2).toBeLessThan(6.5);
    expect(y2).toBeCloseTo(4.5 + ARROW_GEOMETRY.headLength, 1);
    // The head tip sits exactly on the destination center.
    const polys = svg?.querySelectorAll("polygon") ?? [];
    expect(polys[0].getAttribute("points")).toContain("4.5,4.5");
  });

  it("tones map to distinct feedback colors", () => {
    render(
      <ChessBoard
        arrowsEnabled
        arrows={[
          { from: "e2", to: "e4", tone: "correct" },
          { from: "d4", to: "d5", tone: "missed" },
          { from: "a2", to: "a3", tone: "wrong" },
          { from: "h2", to: "h4" },
        ]}
      />,
    );
    const strokes = Array.from(document.querySelectorAll("line")).map((l) =>
      l.getAttribute("stroke"),
    );
    expect(strokes).toEqual(["#16a34a", "#d97706", "#dc2626", "#7c3aed"]);
  });

  it("legacy single arrow still renders", () => {
    render(<ChessBoard arrowsEnabled arrow={{ from: "e2", to: "e4" }} />);
    expect(document.querySelectorAll("line").length).toBe(1);
  });

  it("zero-length and off-board arrows render nothing", () => {
    render(
      <ChessBoard
        arrowsEnabled
        arrows={[
          { from: "e2", to: "e2" },
          { from: "e2", to: "e9" },
        ]}
      />,
    );
    expect(document.querySelectorAll("line").length).toBe(0);
  });

  it("board color depends only on the viewBox, not pixel size", () => {
    const { container } = render(
      <ChessBoard arrowsEnabled arrows={[{ from: "a1", to: "a8" }]} />,
    );
    // a1 center (0.5, 7.5), shaft runs straight up the a-file but stops
    // at the head base; the polygon tip marks a8 center (0.5, 0.5).
    const line = container.querySelector("line");
    expect(line?.getAttribute("x1")).toBe("0.5");
    expect(line?.getAttribute("y1")).toBe("7.5");
    expect(line?.getAttribute("x2")).toBe("0.5");
    const y2 = Number(line?.getAttribute("y2"));
    expect(y2).toBeGreaterThan(0.5);
    expect(y2).toBeCloseTo(0.5 + ARROW_GEOMETRY.headLength, 1);
    expect(container.querySelector("polygon")?.getAttribute("points")).toContain("0.5,0.5");
    expect(screen.getByRole("grid").getAttribute("dir")).toBe("ltr");
  });

  it("head follows orientation: black orientation mirrors coordinates", () => {
    const { container } = render(
      <ChessBoard orientation="black" arrowsEnabled arrows={[{ from: "e2", to: "e4" }]} />,
    );
    // Black orientation flips files/ranks: e2 is (3.5, 1.5), e4 is (3.5, 3.5).
    const line = container.querySelector("line");
    expect(line?.getAttribute("x1")).toBe("3.5");
    expect(line?.getAttribute("y1")).toBe("1.5");
    const y2 = Number(line?.getAttribute("y2"));
    expect(y2).toBeLessThan(3.5);
    expect(y2).toBeCloseTo(3.5 - ARROW_GEOMETRY.headLength, 1);
    expect(container.querySelector("polygon")?.getAttribute("points")).toContain("3.5,3.5");
  });
});

describe("arrow geometry", () => {
  function dist(a: { x: number; y: number }, b: { x: number; y: number }) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  // The central invariant, checked for every shape below: the shaft ends
  // before the tip by ~headLength, and the head is a symmetric triangle
  // around the shaft axis with its tip on the destination.
  function expectLichessStyle(
    geo: NonNullable<ReturnType<typeof computeArrowGeometry>>,
    from: { x: number; y: number },
    to: { x: number; y: number },
  ) {
    expect(geo.start).toEqual(from);
    expect(geo.tip).toEqual(to);
    // Shaft endpoint is before the tip by approximately the head length.
    expect(dist(geo.shaftEnd, geo.tip)).toBeCloseTo(ARROW_GEOMETRY.headLength, 1);
    expect(dist(geo.shaftEnd, geo.tip)).toBeGreaterThan(0);
    // Shaft is colinear: start, shaftEnd and tip on one axis.
    const ux = (to.x - from.x) / dist(from, to);
    const uy = (to.y - from.y) / dist(from, to);
    const along = (geo.shaftEnd.x - from.x) * ux + (geo.shaftEnd.y - from.y) * uy;
    expect(along).toBeGreaterThan(0);
    expect(along).toBeLessThan(dist(from, to));
    // Base corners are symmetric around the base center with the
    // configured head width.
    const mid = {
      x: (geo.baseLeft.x + geo.baseRight.x) / 2,
      y: (geo.baseLeft.y + geo.baseRight.y) / 2,
    };
    expect(dist(mid, geo.shaftEnd)).toBeLessThan(0.05);
    expect(dist(geo.baseLeft, geo.baseRight)).toBeCloseTo(ARROW_GEOMETRY.headWidth, 5);
    // Head edges are longer than the base: a real triangle, not a stub.
    expect(dist(geo.tip, geo.baseLeft)).toBeGreaterThan(ARROW_GEOMETRY.headWidth / 2);
  }

  it("horizontal arrow", () => {
    const geo = computeArrowGeometry({ x: 0.5, y: 4.5 }, { x: 7.5, y: 4.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 0.5, y: 4.5 }, { x: 7.5, y: 4.5 });
    expect(geo!.shaftEnd.y).toBeCloseTo(4.5, 9);
  });

  it("vertical arrow", () => {
    const geo = computeArrowGeometry({ x: 4.5, y: 6.5 }, { x: 4.5, y: 4.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 4.5, y: 6.5 }, { x: 4.5, y: 4.5 });
    expect(geo!.shaftEnd.x).toBeCloseTo(4.5, 9);
  });

  it("diagonal arrow", () => {
    const geo = computeArrowGeometry({ x: 0.5, y: 7.5 }, { x: 7.5, y: 0.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 0.5, y: 7.5 }, { x: 7.5, y: 0.5 });
  });

  it("reverse diagonal arrow", () => {
    const geo = computeArrowGeometry({ x: 7.5, y: 7.5 }, { x: 0.5, y: 0.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 7.5, y: 7.5 }, { x: 0.5, y: 0.5 });
  });

  it("knight-jump arrow", () => {
    const geo = computeArrowGeometry({ x: 4.5, y: 6.5 }, { x: 5.5, y: 4.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 4.5, y: 6.5 }, { x: 5.5, y: 4.5 });
  });

  it("adjacent-square arrow keeps a visible shaft and head", () => {
    const geo = computeArrowGeometry({ x: 4.5, y: 6.5 }, { x: 4.5, y: 5.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 4.5, y: 6.5 }, { x: 4.5, y: 5.5 });
    // Shaft still has real length (head did not swallow it).
    expect(dist(geo!.start, geo!.shaftEnd)).toBeGreaterThan(0.4);
  });

  it("long arrow keeps stable proportions", () => {
    const geo = computeArrowGeometry({ x: 0.5, y: 7.5 }, { x: 0.5, y: 0.5 });
    expect(geo).not.toBeNull();
    expectLichessStyle(geo!, { x: 0.5, y: 7.5 }, { x: 0.5, y: 0.5 });
    expect(dist(geo!.baseLeft, geo!.baseRight)).toBeCloseTo(ARROW_GEOMETRY.headWidth, 5);
  });

  it("zero-length arrow returns null", () => {
    expect(computeArrowGeometry({ x: 4.5, y: 4.5 }, { x: 4.5, y: 4.5 })).toBeNull();
  });

  it("shaft width is constant across arrows", () => {
    const a = computeArrowGeometry({ x: 0.5, y: 7.5 }, { x: 0.5, y: 0.5 });
    const b = computeArrowGeometry({ x: 4.5, y: 6.5 }, { x: 4.5, y: 5.5 });
    expect(a!.shaftWidth).toBe(ARROW_GEOMETRY.shaftWidth);
    expect(b!.shaftWidth).toBe(ARROW_GEOMETRY.shaftWidth);
  });

  it("geometry scales linearly with board size", () => {
    // Board units map to pixels as units/8*boardPx; proportions must hold
    // at every supported size.
    for (const px of [280, 360, 480, 600]) {
      const k = px / 8;
      const geo = computeArrowGeometry({ x: 4.5, y: 6.5 }, { x: 4.5, y: 4.5 })!;
      // Shaft-to-tip gap scales linearly and stays within the head
      // (the 0.02 anti-seam overlap tucks under the opaque triangle).
      const gapPx = dist(geo.shaftEnd, geo.tip) * k;
      expect(gapPx).toBeLessThanOrEqual(ARROW_GEOMETRY.headLength * k);
      expect(gapPx).toBeGreaterThan((ARROW_GEOMETRY.headLength - 0.05) * k);
      expect(geo.shaftWidth * k).toBeCloseTo(ARROW_GEOMETRY.shaftWidth * k, 9);
      expect(dist(geo.baseLeft, geo.baseRight) * k).toBeCloseTo(ARROW_GEOMETRY.headWidth * k, 5);
      // At 280px the head is still several px tall (recognizable).
      expect(ARROW_GEOMETRY.headLength * k).toBeGreaterThan(10);
    }
  });
});
