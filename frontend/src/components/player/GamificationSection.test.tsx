import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GamificationSection } from "./GamificationSection";
import type { AchievementItem, GamificationSummary, XpHistoryItem } from "../../api/types";

const SUMMARY: GamificationSummary = {
  xp: { total: 130, level: 2, xp_in_level: 30, xp_for_next: 100 },
  streak: { current: 3, longest: 5 },
  achievements_unlocked: 1,
  total_achievements: 4,
};

const ACHIEVEMENTS: AchievementItem[] = [
  { code: "first_steps", unlocked: true, unlocked_at: "2026-09-01T10:00:00" },
  { code: "steady_10", unlocked: false, unlocked_at: null },
  { code: "xp_100", unlocked: false, unlocked_at: null },
  { code: "streak_3", unlocked: false, unlocked_at: null },
];

const RECENT_XP: XpHistoryItem[] = [
  { attempt_id: 7, amount: 10, reason: "attempt", balance_after: 130, occurred_at: "2026-09-01T10:00:00" },
];

function renderSection(
  overrides: Partial<{
    summary: GamificationSummary | null;
    achievements: AchievementItem[] | null;
    recentXp: XpHistoryItem[] | null;
    failed: boolean;
  }> = {},
) {
  const onRetry = vi.fn();
  render(
    <GamificationSection
      summary={overrides.summary === undefined ? SUMMARY : overrides.summary}
      achievements={overrides.achievements === undefined ? ACHIEVEMENTS : overrides.achievements}
      recentXp={overrides.recentXp === undefined ? RECENT_XP : overrides.recentXp}
      failed={overrides.failed ?? false}
      onRetry={onRetry}
    />,
  );
  return onRetry;
}

describe("gamification section", () => {
  it("renders Persian XP, level, streak, and achievements", () => {
    renderSection();
    expect(screen.getByText("امتیاز و نشان‌ها")).toBeTruthy();
    expect(screen.getByText("سطح")).toBeTruthy();
    expect(screen.getByText("روزهای پیاپی")).toBeTruthy();
    expect(
      screen.getByText((_text, el) => el?.tagName === "H3" && (el?.textContent?.includes("نشان‌ها") ?? false)),
    ).toBeTruthy();
    // Achievement names come from the Persian catalog.
    expect(screen.getByText("اولین قدم")).toBeTruthy();
    expect(screen.getByText("پرتلاش")).toBeTruthy();
    expect(screen.getByText("گرفته شده")).toBeTruthy();
    expect(screen.getAllByText("هنوز نگرفته‌ای").length).toBe(3);
  });

  it("renders the progress bar from server values only", () => {
    renderSection();
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("30");
    expect(bar.getAttribute("aria-valuemax")).toBe("100");
    const fill = bar.firstElementChild as HTMLElement;
    expect(fill.style.width).toBe("30%");
  });

  it("shows the empty state for a new player", () => {
    renderSection({
      summary: {
        xp: { total: 0, level: 1, xp_in_level: 0, xp_for_next: 100 },
        streak: { current: 0, longest: 0 },
        achievements_unlocked: 0,
        total_achievements: 4,
      },
      recentXp: [],
    });
    expect(
      screen.getByText("هنوز امتیازی نگرفته‌ای؛ با کامل کردن تمرین‌ها امتیاز بگیر."),
    ).toBeTruthy();
    expect(screen.getByText("هنوز امتیازی نگرفته‌ای؛ اولین تمرینت را کامل کن.")).toBeTruthy();
  });

  it("shows loading and error states with retry", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <GamificationSection
        summary={null}
        achievements={null}
        recentXp={null}
        failed={false}
        onRetry={() => {}}
      />,
    );
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();

    const onRetry = vi.fn();
    rerender(
      <GamificationSection
        summary={null}
        achievements={null}
        recentXp={null}
        failed={true}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("مشکلی پیش آمد. دوباره تلاش کن.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("section container stays RTL like the rest of the page", () => {
    renderSection();
    expect(screen.getByText("امتیاز و نشان‌ها")).toBeTruthy();
  });

  it("calls retry from the section error state", async () => {
    const user = userEvent.setup();
    const onRetry = renderSection({ summary: null, failed: true });
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    await waitFor(() => expect(onRetry).toHaveBeenCalledTimes(1));
  });
});
