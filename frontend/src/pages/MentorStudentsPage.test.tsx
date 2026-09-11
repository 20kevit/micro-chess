import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CoachStudentsPage, ParentChildrenPage } from "./MentorStudentsPage";
import { coachApi, parentApi } from "../api/client";
import type { Assignment } from "../api/types";

vi.mock("../api/client", () => ({
  coachApi: {
    students: vi.fn(),
    progress: vi.fn(),
    attempts: vi.fn(),
    ratings: vi.fn(),
    gamification: vi.fn(),
    achievements: vi.fn(),
    analytics: vi.fn(),
    assignments: vi.fn(),
    createAssignment: vi.fn(),
    updateAssignment: vi.fn(),
  },
  parentApi: {
    children: vi.fn(),
    progress: vi.fn(),
    attempts: vi.fn(),
    ratings: vi.fn(),
    gamification: vi.fn(),
    achievements: vi.fn(),
    analytics: vi.fn(),
    assignments: vi.fn(),
  },
  apiDetail: () => "",
}));

const mockedCoach = vi.mocked(coachApi, true);
const mockedParent = vi.mocked(parentApi, true);

const student = { id: 9, username: "kid_01", display_name: "بچه" };

function detailStubs(reads: { progress: ReturnType<typeof vi.fn>; attempts: ReturnType<typeof vi.fn>; ratings: ReturnType<typeof vi.fn>; gamification: ReturnType<typeof vi.fn>; achievements: ReturnType<typeof vi.fn>; analytics: ReturnType<typeof vi.fn>; assignments: ReturnType<typeof vi.fn> }) {
  reads.progress.mockResolvedValue({ attempts: 4, correct: 3, accuracy: 0.75, exercises: [] });
  reads.attempts.mockResolvedValue([]);
  reads.ratings.mockResolvedValue({ items: [] });
  reads.gamification.mockResolvedValue({
    xp: { total: 40, level: 1, xp_in_level: 40, xp_for_next: 60 },
    streak: { current: 2, longest: 2 },
    achievements_unlocked: 1,
    total_achievements: 4,
  });
  reads.achievements.mockResolvedValue({ items: [] });
  reads.analytics.mockResolvedValue({
    totals: { attempts: 4, accuracy: 0.75, active_days: 2 },
    xp: { earned_in_period: 40 },
  });
  reads.assignments.mockResolvedValue([]);
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("coach students page", () => {
  it("lists students with a Persian title and opens a scoped detail", async () => {
    const user = userEvent.setup();
    mockedCoach.students.mockResolvedValue([student]);
    detailStubs(mockedCoach);
    render(
      <MemoryRouter>
        <CoachStudentsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("شاگردان")).toBeTruthy());
    expect(screen.getByText("kid_01")).toBeTruthy();
    await user.click(screen.getByText("بچه"));
    await waitFor(() => expect(screen.getByText("نمای شاگرد")).toBeTruthy());
    expect(mockedCoach.progress).toHaveBeenCalledWith(9);
    expect(screen.getByText("تکالیف")).toBeTruthy();
  });

  it("shows an empty state when the coach has no active students", async () => {
    mockedCoach.students.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <CoachStudentsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("هنوز شاگرد فعالی نداری. اول از صفحه روابط دعوت بفرست.")).toBeTruthy());
  });

  it("creates an assignment for the selected student", async () => {
    const user = userEvent.setup();
    mockedCoach.students.mockResolvedValue([student]);
    detailStubs(mockedCoach);
    mockedCoach.createAssignment.mockResolvedValue({ id: 1 } as Assignment);
    render(
      <MemoryRouter>
        <CoachStudentsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("kid_01")).toBeTruthy());
    await user.click(screen.getByText("بچه"));
    await waitFor(() => expect(screen.getByText("ساخت تکلیف")).toBeTruthy());
    await user.type(screen.getByPlaceholderText("piece-recognition"), "pin");
    await user.click(screen.getByText("ساخت تکلیف"));
    await waitFor(() =>
      expect(mockedCoach.createAssignment).toHaveBeenCalledWith({ student_id: 9, exercise_slug: "pin", note: "" }),
    );
  });
});

describe("parent children page", () => {
  it("lists children with a Persian title and read-only assignments", async () => {
    const user = userEvent.setup();
    mockedParent.children.mockResolvedValue([student]);
    detailStubs(mockedParent);
    mockedParent.assignments.mockResolvedValue([
      {
        id: 1,
        coach_user_id: 3,
        student_user_id: 9,
        relationship_id: 2,
        exercise_slug: "pin",
        note: "daily",
        due_at: null,
        status: "assigned",
        created_at: "",
        updated_at: "",
        completed_at: null,
      } as Assignment,
    ]);
    render(
      <MemoryRouter>
        <ParentChildrenPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("فرزندان")).toBeTruthy());
    await user.click(screen.getByText("بچه"));
    await waitFor(() => expect(screen.getByText("نمای فرزند")).toBeTruthy());
    expect(mockedParent.assignments).toHaveBeenCalledWith(9);
    expect(screen.queryByText("ساخت تکلیف")).toBeNull();
  });

  it("shows an empty state when no child is linked", async () => {
    mockedParent.children.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <ParentChildrenPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("هنوز فرزندی به حسابت وصل نیست. اول از صفحه روابط دعوت بفرست.")).toBeTruthy());
  });
});
