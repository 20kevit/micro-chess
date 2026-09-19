import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Recommendation } from "../../api/types";
import { RecommendationSection } from "./RecommendationSection";

vi.mock("../../api/client", () => ({
  api: {
    recommendation: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

function item(partial?: Partial<Recommendation>): Recommendation {
  return {
    exercise_slug: "captures",
    puzzle_id: 7,
    reason: "WEAK_SKILL",
    assignment_id: null,
    ...partial,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

function renderSection() {
  render(
    <MemoryRouter>
      <RecommendationSection />
    </MemoryRouter>,
  );
}

describe("recommendation section", () => {
  it("shows a Persian loading state first", () => {
    mockedApi.recommendation.mockReturnValue(new Promise(() => {}));
    renderSection();
    expect(screen.getByText("پیشنهاد امروز")).toBeTruthy();
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
  });

  it("shows the suggested exercise with a Persian reason and a training link", async () => {
    mockedApi.recommendation.mockResolvedValue(item());
    renderSection();
    await waitFor(() => expect(screen.getByText("گرفتن مهره‌ها")).toBeTruthy());
    expect(screen.getByText("تقویت نقطه ضعف")).toBeTruthy();
    const link = screen.getByRole("link", { name: /شروع تمرین پیشنهادی/ });
    expect(link.getAttribute("href")).toBe("/exercises/captures");
  });

  it("labels a direct coach assignment in Persian", async () => {
    mockedApi.recommendation.mockResolvedValue(
      item({ exercise_slug: "piece-recognition", reason: "DIRECT_ASSIGNMENT", assignment_id: 3 }),
    );
    renderSection();
    await waitFor(() => expect(screen.getByText("تکلیف مربی")).toBeTruthy());
    expect(screen.getByRole("link", { name: /شروع تمرین پیشنهادی/ }).getAttribute("href")).toBe(
      "/exercises/piece-recognition",
    );
  });

  it("never renders the internal trace", async () => {
    mockedApi.recommendation.mockResolvedValue(item());
    renderSection();
    await waitFor(() => expect(screen.getByText("گرفتن مهره‌ها")).toBeTruthy());
    expect(screen.queryByText(/trace/i)).toBeNull();
    expect(screen.queryByText(/fallback_recency/i)).toBeNull();
    expect(screen.queryByText(/placement_used/i)).toBeNull();
  });

  it("shows a Persian empty state when there is no recommendation", async () => {
    mockedApi.recommendation.mockResolvedValue(null);
    renderSection();
    await waitFor(() =>
      expect(screen.getByText("پیشنهادی برایت نیست؛ یک تمرین را خودت انتخاب کن.")).toBeTruthy(),
    );
  });

  it("shows a Persian error state with retry", async () => {
    const user = userEvent.setup();
    mockedApi.recommendation.mockRejectedValue(new Error("api_error:500"));
    renderSection();
    await waitFor(() => expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy());
    mockedApi.recommendation.mockResolvedValue(item());
    await user.click(screen.getByText("تلاش دوباره"));
    await waitFor(() => expect(screen.getByText("گرفتن مهره‌ها")).toBeTruthy());
  });
});
