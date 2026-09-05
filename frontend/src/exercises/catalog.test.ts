import { describe, expect, it } from "vitest";
import { EXERCISE_CATALOG, getExerciseMeta } from "./catalog";

// The home card buttons ARE the mode selection: each mode links straight
// into its exercise loop with no intermediate screen.
describe("exercise catalog entry modes", () => {
  it("piece-recognition exposes practice and speed entries", () => {
    const meta = getExerciseMeta("piece-recognition");
    expect(meta?.status).toBe("active");
    expect(meta?.route).toBe("/exercises/piece-recognition");
    expect(meta?.modes?.map((m) => m.id)).toEqual(["practice", "speed"]);
  });

  it("mode entries point at distinct mode URLs", () => {
    const meta = getExerciseMeta("piece-recognition");
    const urls = new Set((meta?.modes ?? []).map((m) => `${meta?.route}${m.params}`));
    expect(urls).toEqual(
      new Set(["/exercises/piece-recognition?mode=practice", "/exercises/piece-recognition?mode=speed"]),
    );
  });

  it("other exercises keep a single start action", () => {
    for (const meta of EXERCISE_CATALOG) {
      if (meta.slug === "piece-recognition") continue;
      if (meta.status === "active") expect(meta.route).not.toBeNull();
    }
  });
});
