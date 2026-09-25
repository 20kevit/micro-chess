import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminPuzzle, AnswerContract, ReviewQueueItem } from "../api/types";
import { AdminReviewQueuePage } from "./AdminReviewQueuePage";

vi.mock("../api/client", () => ({
  adminApi: {
    exercises: vi.fn(),
    reviewQueuePage: vi.fn(),
    answerContract: vi.fn(),
    validatePuzzle: vi.fn(),
    reviewPuzzle: vi.fn(),
    approvePuzzle: vi.fn(),
    publishPuzzle: vi.fn(),
    quarantinePuzzle: vi.fn(),
    rejectPuzzle: vi.fn(),
    retirePuzzle: vi.fn(),
    releasePuzzle: vi.fn(),
    restorePuzzle: vi.fn(),
  },
}));

const mockedAdmin = vi.mocked(adminApi);
const FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const CONTRACT: AnswerContract = {
  exercise_slug: "pin",
  answer_type: "ordered_squares",
  answer_fields: [
    { name: "fen", kind: "string", description: "" },
    { name: "pin", kind: "string_list", description: "" },
  ],
  attempt_field: "squares",
  fen_derived: true,
  needs_board: true,
  position_fields: [],
  notes: "",
  validator_registered: true,
  generator_available: false,
  generator_codes: [],
};

function item(id: number, overrides: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    id,
    exercise_slug: "pin",
    status: "validated",
    source: "generated",
    difficulty: 3,
    initial_rating: 1250,
    created_at: "2026-09-01T10:00:00",
    attempts: 12,
    usage_attempts: 12,
    failure_rate: 0.25,
    severity: "high",
    reasons: ["awaiting_review", "high_failure_rate"],
    fen: FEN,
    position_json: {},
    answer_json: { fen: FEN, pin: ["e8", "e6", "e1"] },
    prompt_fa: `پرسش بازبینی ${id}`,
    explanation: `توضیح بازبینی ${id}`,
    source_reference: "pin-v2:88",
    generator_run_id: 88,
    validation_status: "pass",
    latest_validation_status: "pass",
    creator: { user_id: 5, username: "content", display_name: "تیم محتوا" },
    creator_user_id: 5,
    creator_username: "content",
    creator_display_name: "تیم محتوا",
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedAdmin.exercises.mockResolvedValue([{
    slug: "pin",
    title_fa: "آچمز",
    title_en: "Pin",
    description: "",
    is_active: true,
    sort_order: 1,
    puzzle_count: 2,
    published_count: 0,
    needs_review_count: 2,
    success_rate: null,
    low_supply: false,
  }]);
  mockedAdmin.reviewQueuePage.mockResolvedValue({ items: [item(20), item(21)], total: 21 });
  mockedAdmin.answerContract.mockResolvedValue(CONTRACT);
  mockedAdmin.rejectPuzzle.mockResolvedValue({ id: 20, status: "rejected" } as AdminPuzzle);
});

describe("P13 review workspace", () => {
  it("renders total pagination, selectable context, and status-valid actions", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/admin/review-queue"]}>
        <AdminReviewQueuePage />
      </MemoryRouter>,
    );

    await screen.findByText("پرسش بازبینی 20");
    expect(screen.getByText("توضیح بازبینی 20")).toBeTruthy();
    expect(screen.getByText("تیم محتوا")).toBeTruthy();
    expect(screen.getByText("pin-v2:88")).toBeTruthy();
    expect(screen.getByText("صفحه ۱ از ۲ — ۲۱ مورد")).toBeTruthy();
    expect(screen.getByRole("link", { name: "باز کردن برای بازبینی" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "ویرایش" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "پیش‌نمایش و بازی" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "انتشار" })).toBeNull();
    expect(screen.queryByRole("button", { name: "تصویب نهایی" })).toBeNull();
    expect(screen.getByRole("button", { name: "تأیید بازبینی" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /#21/ }));
    expect(await screen.findByText("پرسش بازبینی 21")).toBeTruthy();
    expect(screen.getByText("توضیح بازبینی 21")).toBeTruthy();

    await user.selectOptions(screen.getByLabelText("وضعیت"), "reviewed");
    await waitFor(() => expect(mockedAdmin.reviewQueuePage).toHaveBeenLastCalledWith(expect.objectContaining({
      status: "reviewed",
      page: 1,
      page_size: 20,
    })));
  });

  it("requires a reason and confirmation before rejecting a candidate", async () => {
    const user = userEvent.setup();
    window.confirm = vi.fn(() => true);
    render(
      <MemoryRouter initialEntries={["/admin/review-queue?exercise=pin"]}>
        <AdminReviewQueuePage />
      </MemoryRouter>,
    );

    await screen.findByText("پرسش بازبینی 20");
    const reject = screen.getByRole("button", { name: "رد" });
    expect((reject as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText("دلیل"), "پاسخ نادرست است");
    expect((reject as HTMLButtonElement).disabled).toBe(false);
    await user.click(reject);

    await waitFor(() => expect(mockedAdmin.rejectPuzzle).toHaveBeenCalledWith(20, "پاسخ نادرست است"));
    expect(window.confirm).toHaveBeenCalled();
  });
});
