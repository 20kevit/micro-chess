import { describe, expect, it } from "vitest";
import { buildFen, isValidSquareName, normalizeSquareName, parseFen, splitSquareList } from "./fenEditor";

describe("fenEditor", () => {
  it("parses the starting position", () => {
    const parsed = parseFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    expect(parsed).not.toBeNull();
    expect(parsed?.pieces["e1"]).toBe("K");
    expect(parsed?.pieces["e8"]).toBe("k");
    expect(parsed?.turn).toBe("w");
    expect(parsed?.castling).toBe("KQkq");
  });

  it("rejects malformed FEN strings", () => {
    expect(parseFen(null)).toBeNull();
    expect(parseFen("not-a-fen")).toBeNull();
    expect(parseFen("8/8/8/8/8/8/8/8 x - - 0 1")).toBeNull();
    expect(parseFen("8/8/8/8/8/8/8/9 w - - 0 1")).toBeNull();
  });

  it("round-trips parse and build", () => {
    const fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3";
    const parsed = parseFen(fen);
    expect(parsed).not.toBeNull();
    expect(buildFen(parsed!)).toBe(fen);
  });

  it("builds an empty board", () => {
    const parsed = parseFen("8/8/8/8/8/8/8/8 w - - 0 1");
    expect(parsed).not.toBeNull();
    expect(buildFen(parsed!)).toBe("8/8/8/8/8/8/8/8 w - - 0 1");
  });

  it("validates square names", () => {
    expect(isValidSquareName("e4")).toBe(true);
    expect(isValidSquareName("E4".toLowerCase())).toBe(true);
    expect(isValidSquareName("i9")).toBe(false);
    expect(isValidSquareName("e")).toBe(false);
    expect(normalizeSquareName("  E4 ")).toBe("e4");
    expect(normalizeSquareName("zzz")).toBeNull();
  });

  it("splits square lists with invalid entries reported", () => {
    const { valid, invalid } = splitSquareList("e4, f5 g6 zz");
    expect(valid).toEqual(["e4", "f5", "g6"]);
    expect(invalid).toEqual(["zz"]);
  });
});
