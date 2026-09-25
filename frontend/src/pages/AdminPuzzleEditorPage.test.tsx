import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminPuzzle, AnswerContract } from "../api/types";
import { AnswerEditor, PositionDataEditor } from "../components/content/AnswerEditor";
import { AdminPuzzleEditorPage } from "./AdminPuzzleEditorPage";

vi.mock("../api/client", () => ({
  adminApi: {
    exercises: vi.fn(),
    puzzle: vi.fn(),
    answerContract: vi.fn(),
    puzzleHistory: vi.fn(),
    puzzleUsage: vi.fn(),
    previewValidate: vi.fn(),
    createPuzzle: vi.fn(),
    updatePuzzle: vi.fn(),
    deletePuzzle: vi.fn(),
  },
}));

const mockedAdmin = vi.mocked(adminApi);
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const NEW_FEN = "8/8/8/8/8/8/4k3/4K3 w - - 0 1";

function contract(overrides: Partial<AnswerContract> = {}): AnswerContract {
  return {
    exercise_slug: "piece-recognition",
    answer_type: "squares",
    answer_fields: [
      { name: "squares", kind: "string_list", description: "", item_hint: "e4" },
      { name: "target", kind: "string", description: "" },
    ],
    attempt_field: "selected_squares",
    fen_derived: false,
    needs_board: true,
    position_fields: [],
    notes: "",
    validator_registered: true,
    generator_available: false,
    generator_codes: [],
    ...overrides,
  };
}

function puzzle(overrides: Partial<AdminPuzzle> = {}): AdminPuzzle {
  return {
    id: 7,
    exercise_slug: "piece-recognition",
    status: "draft",
    fen: START,
    position_json: { from: "e4" },
    answer_json: { squares: ["a2"], target: "white-pawn" },
    hint_json: { operator: ">", message: "ثابت" },
    prompt_fa: "مهره هدف را پیدا کن",
    explanation: "توضیح",
    initial_rating: 1200,
    is_published: false,
    is_archived: false,
    published_at: null,
    created_at: "2026-09-01T10:00:00",
    source: "manual",
    source_reference: "manual-batch-3",
    generator_run_id: null,
    difficulty: 2,
    target_rating: 1250,
    retired_at: null,
    ...overrides,
  };
}

function ControlledAnswerEditor({ contract, onChange }: { contract: AnswerContract; onChange: (value: Record<string, unknown>) => void }) {
  const [value, setValue] = useState<Record<string, unknown>>({ squares: ["a2"] });
  return (
    <AnswerEditor
      contract={contract}
      answer={value}
      onChange={(next) => {
        setValue(next);
        onChange(next);
      }}
    />
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedAdmin.exercises.mockResolvedValue([{
    slug: "piece-recognition",
    title_fa: "تشخیص مهره",
    title_en: "Piece Recognition",
    description: "",
    is_active: true,
    sort_order: 1,
    puzzle_count: 1,
    published_count: 0,
    needs_review_count: 0,
    success_rate: null,
    low_supply: false,
  }]);
});

describe("P13 puzzle editor", () => {
  it("preserves stored metadata and synchronizes the derived answer FEN", async () => {
    const user = userEvent.setup();
    const row = puzzle({
      exercise_slug: "pin",
      answer_json: { fen: START, pin: ["e8", "e6", "e1"] },
    });
    mockedAdmin.puzzle.mockResolvedValue(row);
    mockedAdmin.answerContract.mockResolvedValue(contract({
      exercise_slug: "pin",
      answer_type: "ordered_squares",
      answer_fields: [
        { name: "fen", kind: "string", description: "" },
        { name: "pin", kind: "string_list", description: "" },
      ],
      attempt_field: "squares",
      fen_derived: true,
    }));
    mockedAdmin.puzzleHistory.mockResolvedValue({ puzzle_id: 7, status: "draft", transitions: [], validations: [], reviews: [] });
    mockedAdmin.puzzleUsage.mockResolvedValue({
      puzzle_id: 7,
      attempts: 0,
      by_result: {},
      success_rate: null,
      avg_duration_ms: null,
      recent_attempts: 20,
    });
    mockedAdmin.updatePuzzle.mockImplementation(async (_id, patch) => ({
      ...row,
      ...patch,
    } as AdminPuzzle));

    render(
      <MemoryRouter initialEntries={["/admin/puzzles/7/edit"]}>
        <Routes>
          <Route path="/admin/puzzles/:id/edit" element={<AdminPuzzleEditorPage />} />
          <Route path="/admin/puzzles/:id" element={<div>{row.prompt_fa}</div>} />
        </Routes>
      </MemoryRouter>,
    );

     await screen.findByText("پاسخ مورد انتظار");
     await waitFor(() => expect((screen.getByRole("button", { name: "ذخیره تغییرات" }) as HTMLButtonElement).disabled).toBe(false));
     expect(screen.getByText("حذف پیش‌نویس")).toBeTruthy();
    expect(screen.queryByLabelText(/شناسه معما/)).toBeNull();

    const fenInput = screen.getByLabelText("FEN");
    await user.clear(fenInput);
    await user.type(fenInput, NEW_FEN);
    await user.click(screen.getByText("اعمال FEN"));
    await user.click(screen.getByText("ذخیره تغییرات"));

    await waitFor(() => expect(mockedAdmin.updatePuzzle).toHaveBeenCalled());
    const patch = mockedAdmin.updatePuzzle.mock.calls[0][1];
    expect(patch).toEqual(expect.objectContaining({
      fen: NEW_FEN,
      answer_json: { fen: NEW_FEN, pin: ["e8", "e6", "e1"] },
      target_rating: 1250,
      difficulty: 2,
      initial_rating: 1200,
    }));
    expect(patch).not.toHaveProperty("position_json");
    expect(patch).not.toHaveProperty("hint_json");
    expect(patch).not.toHaveProperty("source_reference");
  });

  it("renders every declared target, origin, and profile control", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const legalContract = contract({
      exercise_slug: "legal-destinations",
      answer_fields: [
        { name: "squares", kind: "string_list", description: "" },
        { name: "from", kind: "string", description: "" },
        { name: "profile", kind: "string", description: "" },
      ],
    });
    const pieceContract = contract({
      answer_fields: [
        { name: "squares", kind: "string_list", description: "" },
        { name: "target", kind: "string", description: "" },
      ],
    });

    const view = render(<ControlledAnswerEditor contract={legalContract} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("شروع · from"), { target: { value: "d4" } });
    expect(onChange).toHaveBeenLastCalledWith({ squares: ["a2"], from: "d4" });
    await user.selectOptions(screen.getByLabelText("دسته · profile"), "ignore-enemy-attacks");
    await user.selectOptions(screen.getByLabelText("دسته · profile"), "standard");
    expect(onChange).toHaveBeenLastCalledWith({ squares: ["a2"], from: "d4", profile: "standard" });
    view.unmount();

    render(<AnswerEditor contract={pieceContract} answer={{ squares: ["a2"] }} onChange={onChange} />);
    expect(screen.getByText(/target/)).toBeTruthy();
  });

  it("keeps chip removal disabled in read-only mode", () => {
    const onChange = vi.fn();
    render(
      <AnswerEditor
        contract={contract()}
        answer={{ squares: ["a2"], target: "white-pawn" }}
        onChange={onChange}
        disabled
      />,
    );
    const chip = screen.getByRole("button", { name: "1. a2" });
    expect((chip as HTMLButtonElement).disabled).toBe(true);
  });

  it("renders contract position metadata fields", () => {
    const positionContract = contract({
      exercise_slug: "pathfinding-obstacles",
      answer_fields: [{ name: "from", kind: "string", description: "" }],
      position_fields: [{ name: "enemies", kind: "enemy_list", description: "" }],
    });
    render(
      <PositionDataEditor
        contract={positionContract}
        value={{ enemies: [{ square: "e4", kind: "rook" }] }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("enemies")).toBeTruthy();
    expect(screen.getByDisplayValue("e4")).toBeTruthy();
  });

  it("does not offer deletion when validation history exists", async () => {
    const row = puzzle();
    mockedAdmin.puzzle.mockResolvedValue(row);
    mockedAdmin.answerContract.mockResolvedValue(contract());
    mockedAdmin.puzzleHistory.mockResolvedValue({
      puzzle_id: 7,
      status: "draft",
      transitions: [],
      validations: [{ id: 1, validator_version: "1", status: "fail", result: { errors: [] }, validated_by_user_id: 2, created_at: "2026-09-01" }],
      reviews: [],
    });
    mockedAdmin.puzzleUsage.mockResolvedValue({
      puzzle_id: 7,
      attempts: 0,
      by_result: {},
      success_rate: null,
      avg_duration_ms: null,
      recent_attempts: 20,
    });

    render(
      <MemoryRouter initialEntries={["/admin/puzzles/7/edit"]}>
        <Routes><Route path="/admin/puzzles/:id/edit" element={<AdminPuzzleEditorPage />} /></Routes>
      </MemoryRouter>,
    );

    await screen.findByText("پاسخ مورد انتظار");
    expect(screen.queryByText("حذف پیش‌نویس")).toBeNull();
    expect(screen.getByText(/سابقه اعتبارسنجی/)).toBeTruthy();
  });
});
