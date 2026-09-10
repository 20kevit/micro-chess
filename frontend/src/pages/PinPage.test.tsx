import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PinPage } from "./PinPage";
import type { AttemptResponse, Puzzle } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../api/client")>();
  return { ...orig, api: {} };
});
import { api } from "../api/client";

const mockedApi = vi.mocked(api, true);

// First pin seed: Re1 pins Ne6 to Ke8 (absolute pin).
const FEN = "4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1";

function puzzle(id: number): Puzzle {
  return {
    id,
    exercise_slug: "pin",
    fen: FEN,
    position_json: { fen: FEN, mode: "standard" },
    hint_json: { hints: [] },
    prompt_fa: "سه مهره آچمز را به ترتیب انتخاب کن.",
    explanation: "",
    initial_rating: 800,
    is_published: true,
    is_archived: false,
  };
}

function attempt(puzzleId: number): AttemptResponse {
  return {
    id: puzzleId * 10,
    puzzle_id: puzzleId,
    exercise_slug: "pin",
    mode: "practice",
    result: "correct",
    score: 1.0,
    feedback_key: "feedback.correct",
    rating_delta: null,
    detail: { correct: ["e1", "e6", "e8"], missed: [], wrong: [] },
    hints_used: [],
    started_at: null,
    duration_ms: 100,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/exercises/pin"]}>
      <Routes>
        <Route path="/exercises/pin" element={<PinPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listPuzzles = vi.fn().mockResolvedValue([puzzle(1)]);
  mockedApi.submitAttempt = vi.fn().mockResolvedValue(attempt(1));
});

describe("Pin direct play", () => {
  it("opens the board immediately with no entry screen or mode selector", async () => {
    renderPage();
    // Playable board right away: prompt + step labels, pieces on squares.
    expect(await screen.findByText("سه مهره آچمز را به ترتیب انتخاب کن.")).toBeTruthy();
    expect(screen.getByText("۱. مهره آچمزکننده", { exact: false })).toBeTruthy();
    expect(screen.getByText("۲. مهره آچمزشده", { exact: false })).toBeTruthy();
    expect(screen.getByText("۳. مهره پشتی", { exact: false })).toBeTruthy();
    expect(screen.getByRole("gridcell", { name: "e1" })).toBeTruthy();
    // No old two-mode flow: no start button, no mode picker.
    expect(screen.queryByRole("button", { name: "شروع" })).toBeNull();
    expect(screen.queryByText("حالت")).toBeNull();
    expect(screen.queryByText("امتیازی")).toBeNull();
  });

  it("submit stays disabled until three pieces are picked", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("سه مهره آچمز را به ترتیب انتخاب کن.");
    const submit = screen.getByRole("button", { name: "بررسی جواب" });
    expect(submit.hasAttribute("disabled")).toBe(true);
    await user.click(screen.getByRole("gridcell", { name: "e1" }));
    await user.click(screen.getByRole("gridcell", { name: "e6" }));
    expect(submit.hasAttribute("disabled")).toBe(true);
    await user.click(screen.getByRole("gridcell", { name: "e8" }));
    expect(submit.hasAttribute("disabled")).toBe(false);
  });

  it("submits the ordered [pinner, pinned, behind] triplet in practice mode", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("سه مهره آچمز را به ترتیب انتخاب کن.");
    await user.click(screen.getByRole("gridcell", { name: "e1" }));
    await user.click(screen.getByRole("gridcell", { name: "e6" }));
    await user.click(screen.getByRole("gridcell", { name: "e8" }));
    // Step progress shows the tapped order.
    const stepText = (n: string) =>
      screen.getByText((_, el) => el?.tagName === "P" && (el.textContent ?? "").startsWith(n)).textContent ?? "";
    expect(stepText("۱.")).toContain("e1");
    expect(stepText("۲.")).toContain("e6");
    expect(stepText("۳.")).toContain("e8");
    await user.click(screen.getByRole("button", { name: "بررسی جواب" }));
    expect(mockedApi.submitAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        puzzle_id: 1,
        answer: { squares: ["e1", "e6", "e8"] },
        mode: "practice",
      }),
    );
  });

  it("tapping a picked square deselects it", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("سه مهره آچمز را به ترتیب انتخاب کن.");
    const e1 = screen.getByRole("gridcell", { name: "e1" });
    await user.click(e1);
    expect(e1.getAttribute("aria-pressed")).toBe("true");
    await user.click(e1);
    expect(e1.getAttribute("aria-pressed")).toBe("false");
  });
});
