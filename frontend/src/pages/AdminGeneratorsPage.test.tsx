import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminPuzzle, AnswerContract, GeneratorRun } from "../api/types";
import { AdminGeneratorsPage } from "./AdminGeneratorsPage";

vi.mock("../api/client", () => ({
  adminApi: {
    generators: vi.fn(),
    exercises: vi.fn(),
    generatorRunsPage: vi.fn(),
    runGenerator: vi.fn(),
    puzzle: vi.fn(),
    answerContract: vi.fn(),
    previewValidate: vi.fn(),
    validatePuzzle: vi.fn(),
    reviewPuzzle: vi.fn(),
    rejectPuzzle: vi.fn(),
    publishPuzzle: vi.fn(),
  },
}));

const mockedAdmin = vi.mocked(adminApi);
const FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const CONTRACT: AnswerContract = {
  exercise_slug: "piece-recognition",
  answer_type: "squares",
  answer_fields: [
    { name: "squares", kind: "string_list", description: "" },
    { name: "target", kind: "string", description: "" },
  ],
  attempt_field: "selected_squares",
  fen_derived: false,
  needs_board: true,
  position_fields: [],
  notes: "",
  validator_registered: true,
  generator_available: true,
  generator_codes: ["piece-v1"],
};

function candidate(overrides: Partial<AdminPuzzle> = {}): AdminPuzzle {
  return {
    id: 41,
    exercise_slug: "piece-recognition",
    status: "validated",
    fen: FEN,
    position_json: {},
    answer_json: { squares: ["a2"], target: "white-pawn" },
    hint_json: {},
    prompt_fa: "پرسش نامزد",
    explanation: "توضیح کامل نامزد",
    initial_rating: 1200,
    is_published: false,
    is_archived: false,
    published_at: null,
    created_at: "2026-09-10T12:00:00",
    source: "generated",
    source_reference: "piece-v1:12",
    generator_run_id: 12,
    difficulty: 3,
    target_rating: 1300,
    retired_at: null,
    ...overrides,
  };
}

function run(): GeneratorRun {
  return {
    id: 12,
    generator_code: "piece-v1",
    generator_version: "1.0.0",
    exercise_slug: "piece-recognition",
    status: "completed",
    requested_count: 1,
    generated_count: 1,
    validated_count: 1,
    accepted_count: 1,
    rejected_count: 0,
    seed: 22,
    target_rating: 1300,
    difficulty: 3,
    config: {},
    result: { accepted_puzzle_ids: [41], rejected: [] },
    error: "",
    requested_by_user_id: 5,
    created_at: "2026-09-10T12:00:00",
    updated_at: "2026-09-10T12:00:01",
    completed_at: "2026-09-10T12:00:01",
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedAdmin.generators.mockResolvedValue([{
    code: "piece-v1",
    exercise_slug: "piece-recognition",
    version: "1.0.0",
    description: "",
    config_schema: {},
    status: "active",
  }]);
  mockedAdmin.exercises.mockResolvedValue([
    {
      slug: "piece-recognition",
      title_fa: "تشخیص مهره",
      title_en: "Piece Recognition",
      description: "",
      is_active: true,
      sort_order: 1,
      puzzle_count: 0,
      published_count: 0,
      needs_review_count: 0,
      success_rate: null,
      low_supply: false,
    },
    {
      slug: "pin",
      title_fa: "آچمز",
      title_en: "Pin",
      description: "",
      is_active: true,
      sort_order: 2,
      puzzle_count: 0,
      published_count: 0,
      needs_review_count: 0,
      success_rate: null,
      low_supply: false,
    },
  ]);
  mockedAdmin.generatorRunsPage.mockResolvedValue({ items: [], total: 0 });
  mockedAdmin.runGenerator.mockResolvedValue(run());
  mockedAdmin.puzzle.mockResolvedValue(candidate());
  mockedAdmin.answerContract.mockResolvedValue(CONTRACT);
  mockedAdmin.previewValidate.mockResolvedValue({ ok: true, errors: [], content_hash: "hash" });
  mockedAdmin.validatePuzzle.mockResolvedValue(candidate({ status: "validated" }));
  mockedAdmin.reviewPuzzle.mockResolvedValue(candidate({ status: "reviewed" }));
  mockedAdmin.rejectPuzzle.mockResolvedValue(candidate({ status: "rejected" }));
});

describe("P13 one-candidate generator", () => {
  it("generates one candidate, validates and accepts it to reviewed without publishing", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/admin/generators?exercise=piece-recognition"]}>
        <AdminGeneratorsPage />
      </MemoryRouter>,
    );

    await screen.findByText("ساخت نامزد بعدی");
    expect(screen.queryByLabelText("تعداد")).toBeNull();
    await user.click(screen.getByText("ساخت نامزد بعدی"));

    await screen.findByText("پرسش نامزد");
    expect(screen.getByText("توضیح کامل نامزد")).toBeTruthy();
    expect(screen.getByText("مولد")).toBeTruthy();
    expect(screen.getByText("piece-v1:12")).toBeTruthy();
    expect(screen.getByText("اعتبارسنجی موفق بود")).toBeTruthy();
    expect(mockedAdmin.runGenerator).toHaveBeenCalledWith("piece-v1", expect.objectContaining({ count: 1 }));

    await user.click(screen.getByText("پذیرش و ادامه فرایند"));
    await waitFor(() => expect(mockedAdmin.reviewPuzzle).toHaveBeenCalledWith(41, { decision: "approve", notes: "" }));
    expect(mockedAdmin.validatePuzzle).toHaveBeenCalledWith(41);
    expect(mockedAdmin.publishPuzzle).not.toHaveBeenCalled();
    expect(mockedAdmin.validatePuzzle.mock.invocationCallOrder[0]).toBeLessThan(mockedAdmin.reviewPuzzle.mock.invocationCallOrder[0]);

    await user.click(screen.getByText("ساخت نامزد بعدی"));
    await screen.findByText("پرسش نامزد");
    await user.type(screen.getByLabelText("دلیل"), "محتوای تکراری است");
    window.confirm = vi.fn(() => true);
    await user.click(screen.getByText("رد نامزد"));
    await waitFor(() => expect(mockedAdmin.rejectPuzzle).toHaveBeenCalledWith(41, "محتوای تکراری است"));
    expect(window.confirm).toHaveBeenCalled();
  });

  it("shows the exact prepared message for an unsupported exercise", async () => {
    mockedAdmin.generators.mockResolvedValue([]);
    render(
      <MemoryRouter initialEntries={["/admin/generators?exercise=pin"]}>
        <AdminGeneratorsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("برای این تمرین مولد خودکار وجود ندارد؛ معما را می‌توانید به‌صورت دستی ایجاد کنید.")).toBeTruthy();
  });
});
