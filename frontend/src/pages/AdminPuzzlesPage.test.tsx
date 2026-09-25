import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "../api/client";
import type { AdminPuzzle } from "../api/types";
import { AdminPuzzlesPage } from "./AdminPuzzlesPage";

vi.mock("../api/client", () => ({
  adminApi: {
    exercises: vi.fn(),
    puzzlesPage: vi.fn(),
    bulkPuzzles: vi.fn(),
  },
}));

const mockedAdmin = vi.mocked(adminApi);
const FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function row(id: number, overrides: Partial<AdminPuzzle> = {}): AdminPuzzle {
  return {
    id,
    exercise_slug: "pin",
    status: id === 1 ? "draft" : "published",
    fen: FEN,
    position_json: {},
    answer_json: {},
    hint_json: {},
    prompt_fa: `پرسش ${id}`,
    explanation: "",
    initial_rating: 1200 + id,
    is_published: id === 2,
    is_archived: false,
    published_at: id === 2 ? "2026-09-02T10:00:00" : null,
    created_at: "2026-09-01T10:00:00",
    source: id === 1 ? "manual" : "generated",
    source_reference: null,
    generator_run_id: id === 2 ? 9 : null,
    difficulty: id,
    target_rating: 1200,
    retired_at: null,
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
    published_count: 1,
    needs_review_count: 0,
    success_rate: null,
    low_supply: false,
  }]);
  mockedAdmin.puzzlesPage.mockResolvedValue({ items: [row(1), row(2)], total: 41 });
});

describe("P13 puzzle library", () => {
  it("renders the responsive data table and server-driven filters", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );

    const table = await screen.findByRole("table");
    expect(table).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "شناسه معما" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "منبع" })).toBeTruthy();
    expect(screen.getAllByText("پیش‌نویس").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("منتشرشده").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("دستی").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("مولد").length).toBeGreaterThanOrEqual(2);

    await user.selectOptions(screen.getByLabelText("دشواری"), "2");
    await user.type(screen.getByPlaceholderText("جست‌وجو در صورت سؤال، تمرین یا FEN…"), "آچمز");

    await waitFor(() => expect(mockedAdmin.puzzlesPage).toHaveBeenLastCalledWith(expect.objectContaining({
      exercise: undefined,
      status: undefined,
      difficulty: 2,
      source: undefined,
      search: "آچمز",
      page: 1,
      page_size: 20,
    })));

    expect(screen.getByText("صفحه ۱ از ۳ — ۴۱ مورد")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "صفحه بعد" }));
    await waitFor(() => expect(mockedAdmin.puzzlesPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("keeps selection across pages and requires a reason for destructive bulk actions", async () => {
    const user = userEvent.setup();
    window.confirm = vi.fn(() => true);
    mockedAdmin.bulkPuzzles.mockResolvedValue({
      action: "quarantine",
      succeeded: [],
      failed: [{ id: 1, error: "invalid_transition" }],
    });
    render(
      <MemoryRouter initialEntries={["/admin/puzzles"]}>
        <AdminPuzzlesPage />
      </MemoryRouter>,
    );

    await screen.findByRole("table");
    await user.click(screen.getByRole("checkbox", { name: "شناسه معما 1" }));
    const quarantine = screen.getByRole("button", { name: /^قرنطینه/ });
    expect((quarantine as HTMLButtonElement).disabled).toBe(true);

    await user.type(screen.getByLabelText("دلیل"), "بازبینی ایمنی");
    expect((quarantine as HTMLButtonElement).disabled).toBe(false);
    await user.click(quarantine);

    await waitFor(() => expect(mockedAdmin.bulkPuzzles).toHaveBeenCalledWith({
      puzzle_ids: [1],
      action: "quarantine",
      reason: "بازبینی ایمنی",
    }));
    expect(window.confirm).toHaveBeenCalled();
    expect(await screen.findByText(/برخی موارد انجام نشد/)).toBeTruthy();
    expect(screen.getByText("انتخاب‌شده: ۱")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "صفحه بعد" }));
    await waitFor(() => expect(mockedAdmin.puzzlesPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
    expect(screen.getByText("انتخاب‌شده: ۱")).toBeTruthy();
  });
});
