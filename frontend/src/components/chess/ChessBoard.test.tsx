import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  arrowKey,
  arrowToUci,
  ChessBoard,
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
  it("renders every arrow as a line in board-fraction coordinates", () => {
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
    const lines = svg?.querySelectorAll("line") ?? [];
    expect(lines.length).toBe(2);
    // e-file center is x=4.5 in board units regardless of pixel size, so
    // arrows stay aligned when the board resizes (SVG scales the viewBox).
    expect(lines[0].getAttribute("x1")).toBe("4.5");
    expect(lines[0].getAttribute("y1")).toBe("6.5");
    expect(lines[0].getAttribute("y2")).toBe("4.5");
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
    // a1 center (0.5, 7.5) -> a8 center (0.5, 0.5): pure geometry.
    const line = container.querySelector("line");
    expect(line?.getAttribute("x1")).toBe("0.5");
    expect(line?.getAttribute("y1")).toBe("7.5");
    expect(line?.getAttribute("x2")).toBe("0.5");
    expect(line?.getAttribute("y2")).toBe("0.5");
    expect(screen.getByRole("grid").getAttribute("dir")).toBe("ltr");
  });
});
