// Phase 12 content-management UI: board editor, typed answer editors,
// content health, and the puzzle detail workspace. Components render
// server-shaped fixtures; the backend stays authoritative (covered by
// pytest); these tests assert presentation and transport wiring only.
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import { AnswerEditor, type AnswerContract } from "../components/content/AnswerEditor";
import { BoardEditor } from "../components/content/BoardEditor";
import { AdminContentHealthPage } from "./AdminContentHealthPage";
import { AdminPuzzleDetailPage } from "./AdminPuzzleDetailPage";
import { t } from "../i18n";

vi.mock("../api/client", () => ({
  adminApi: {
    puzzle: vi.fn(),
    puzzleHistory: vi.fn(),
    puzzleUsage: vi.fn(),
    answerContract: vi.fn(),
    validatePuzzle: vi.fn(),
    updatePuzzle: vi.fn(),
    reviewPuzzle: vi.fn(),
    approvePuzzle: vi.fn(),
    publishPuzzle: vi.fn(),
    quarantinePuzzle: vi.fn(),
    releasePuzzle: vi.fn(),
    rejectPuzzle: vi.fn(),
    retirePuzzle: vi.fn(),
    contentHealth: vi.fn(),
  },
}));

const mockedAdmin = vi.mocked(adminApi, true);

beforeEach(() => {
  vi.resetAllMocks();
});

const PIN_CONTRACT: AnswerContract = {
  exercise_slug: "pin",
  answer_type: "ordered_squares",
  answer_fields: [{ name: "pin", kind: "string_list", description: "Pin triplet" }],
  attempt_field: "squares",
  fen_derived: true,
  needs_board: true,
  position_fields: [],
  notes: "",
  validator_registered: true,
  generator_available: false,
  generator_codes: [],
};

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

describe("board editor", () => {
  it("renders the palette, side to move, and FEN controls", () => {
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <BoardEditor fen={START} onChange={onChange} />
      </MemoryRouter>,
    );
    expect(screen.getByText("نوبت حرکت")).toBeTruthy();
    expect(screen.getByText("حق قلعه")).toBeTruthy();
    expect(screen.getByText("اعمال FEN")).toBeTruthy();
    expect(screen.getByText("چرخش صفحه")).toBeTruthy();
  });

  it("switching side to move emits an updated FEN", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <BoardEditor fen={START} onChange={onChange} />
      </MemoryRouter>,
    );
    await user.click(screen.getByText("سیاه"));
    expect(onChange).toHaveBeenCalledOnce();
    expect(String(onChange.mock.calls[0][0]).split(" ")[1]).toBe("b");
  });

  it("rejects an invalid FEN paste without emitting", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <BoardEditor fen={START} onChange={onChange} />
      </MemoryRouter>,
    );
    const box = screen.getByLabelText("FEN");
    await user.clear(box);
    await user.type(box, "not-a-fen");
    await user.click(screen.getByText("اعمال FEN"));
    expect(screen.getByText("FEN نامعتبر است")).toBeTruthy();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("answer editor", () => {
  it("edits ordered squares with positional labels", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <AnswerEditor contract={PIN_CONTRACT} answer={{ pin: ["e8"] }} onChange={onChange} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/مهره آچمزکننده/).textContent).toBeTruthy();
    await user.type(screen.getByPlaceholderText("e8"), "e6");
    await user.click(screen.getByText("+"));
    expect(onChange).toHaveBeenCalledWith({ pin: ["e8", "e6"] });
  });

  it("flags malformed squares without emitting", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <AnswerEditor contract={PIN_CONTRACT} answer={{ pin: [] }} onChange={onChange} />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("e8"), "zz");
    await user.click(screen.getByText("+"));
    expect(screen.getByText(/مقدار نامعتبر است/).textContent).toContain("zz");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("keeps derived checkmate choices read-only", () => {
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <AnswerEditor
          contract={{ ...PIN_CONTRACT, exercise_slug: "is-checkmate", answer_type: "choice", fen_derived: true }}
          answer={{}}
          onChange={onChange}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(t("admin.answerDerivedNote"))).toBeTruthy();
    expect(screen.queryByText("check")).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("content health page", () => {
  it("shows the empty state and attention filter", async () => {
    mockedAdmin.contentHealth.mockResolvedValue({
      low_supply_threshold: 5,
      exercises: [],
      attention_count: 0,
    });
    render(
      <MemoryRouter>
        <AdminContentHealthPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("موردی نیست.")).toBeTruthy());
    expect(screen.getAllByText("سلامت محتوا").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/تمرین نیازمند توجه/).textContent).toBeTruthy();
  });

  it("lists exercises with supply states and links", async () => {
    mockedAdmin.contentHealth.mockResolvedValue({
      low_supply_threshold: 5,
      exercises: [
        {
          slug: "pin", title_fa: "آچمز", is_active: true, published: 0, total: 2,
          needs_review: 2, quarantined: 0, attempts: 0, success_rate: null,
          generator_available: false, generator_codes: [],
          supply_state: "critical", reasons: ["low_supply", "no_generator"],
        },
      ],
      attention_count: 1,
    });
    render(
      <MemoryRouter>
        <AdminContentHealthPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("آچمز")).toBeTruthy());
    expect(screen.getByText("بحرانی")).toBeTruthy();
    expect(screen.getByText(/کمبود معمای منتشرشده/).textContent).toBeTruthy();
  });
});

describe("puzzle detail workspace", () => {
  function mockDetail() {
    mockedAdmin.puzzle.mockResolvedValue({
      id: 1, exercise_slug: "pin", status: "draft", fen: START, position_json: {},
      answer_json: { fen: START, pin: ["e8", "e2", "e1"] }, hint_json: {},
      prompt_fa: "سوال", explanation: "", initial_rating: 1200,
      is_published: false, is_archived: false, published_at: null,
      created_at: "", source: "generated", source_reference: null,
      generator_run_id: 4, difficulty: 3, target_rating: null, retired_at: null,
    });
    mockedAdmin.puzzleHistory.mockResolvedValue({
      puzzle_id: 1, status: "draft", transitions: [], validations: [], reviews: [],
    });
    mockedAdmin.puzzleUsage.mockResolvedValue({
      puzzle_id: 1, attempts: 0, by_result: {}, success_rate: null,
      avg_duration_ms: null, recent_attempts: 20,
    });
    mockedAdmin.answerContract.mockResolvedValue({
      ...PIN_CONTRACT,
      validator_registered: true,
      generator_available: false,
      generator_codes: [],
    });
  }

  it("renders preview, answer, lifecycle, usage, and history sections", async () => {
    mockDetail();
    render(
      <MemoryRouter initialEntries={["/admin/puzzles/1"]}>
        <Routes>
          <Route path="/admin/puzzles/:id" element={<AdminPuzzleDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/جزئیات معما/).textContent).toBeTruthy());
    expect(screen.getByText("پیش‌نمایش")).toBeTruthy();
    expect(screen.getByText("پاسخ مورد انتظار")).toBeTruthy();
    expect(screen.getByText("ordered_squares")).toBeTruthy();
    expect(screen.getAllByText("اعتبارسنجی").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("ویرایش")).toBeTruthy();
    expect(screen.getByText("سوابق چرخه")).toBeTruthy();
  });
});
