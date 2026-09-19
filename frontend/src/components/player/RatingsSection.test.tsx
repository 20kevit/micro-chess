import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { PlayerRating } from "../../api/types";
import { RatingsSection } from "./RatingsSection";

function rating(overrides: Partial<PlayerRating> = {}): PlayerRating {
  return {
    exercise: "piece-recognition",
    rating: 1216.5,
    rating_deviation: 339.5,
    provisional: true,
    attempts_count: 3,
    updated_at: "2026-09-11T10:00:00",
    ...overrides,
  };
}

function renderSection(props: {
  ratings: PlayerRating[] | null;
  failed: boolean;
  onRetry?: () => void;
}) {
  render(
    <MemoryRouter>
      <RatingsSection ratings={props.ratings} failed={props.failed} onRetry={props.onRetry ?? (() => {})} />
    </MemoryRouter>,
  );
}

describe("ratings section", () => {
  it("shows a Persian loading state", () => {
    renderSection({ ratings: null, failed: false });
    expect(screen.getByText("بازی‌های امتیازی")).toBeTruthy();
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
  });

  it("shows a Persian empty state when the player has no ratings", () => {
    renderSection({ ratings: [], failed: false });
    expect(screen.getByText("بازی‌های امتیازی")).toBeTruthy();
    expect(
      screen.getByText("هنوز بازی امتیازی انجام نداده‌ای؛ بعد از اولین بازی امتیازی، فعالیتت را اینجا می‌بینی."),
    ).toBeTruthy();
  });

  it("shows a Persian error state with retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    renderSection({ ratings: null, failed: true, onRetry });
    expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders per-exercise rated activity without numeric ratings", () => {
    renderSection({
      ratings: [rating(), rating({ exercise: "pin", rating: 1300, provisional: false, attempts_count: 12 })],
      failed: false,
    });
    // Persian exercise titles come from the catalog, not the raw slug.
    expect(screen.getByText("تشخیص مهره")).toBeTruthy();
    expect(screen.getByText("آچمز")).toBeTruthy();
    expect(screen.getByText("موقت")).toBeTruthy();
    // Persian-digit rated-game counts, one row per exercise.
    expect(screen.getByText("۳ بازی امتیازی")).toBeTruthy();
    expect(screen.getByText("۱۲ بازی امتیازی")).toBeTruthy();
    // Internal rating numbers stay hidden from players (P9 product rule).
    expect(screen.queryByText("۱۲۱۶٫۵")).toBeNull();
    expect(screen.queryByText("۱۳۰۰")).toBeNull();
  });

  it("keeps anonymous behavior out of scope: no login prompt here", () => {
    // The page is behind RequireAuth; this section only handles its own
    // loading/empty/error/data states and never renders auth UI.
    renderSection({ ratings: [], failed: false });
    expect(screen.queryByText("ورود")).toBeNull();
  });
});
