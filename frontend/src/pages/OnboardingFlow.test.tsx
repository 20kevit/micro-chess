import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingPage } from "./OnboardingPage";
import { VerifyPage } from "./VerifyPage";
import { onboardingApi, verificationApi, notifyApi } from "../api/client";

vi.mock("../api/client", () => ({
  onboardingApi: { get: vi.fn(), save: vi.fn(), placement: vi.fn(), completePlacement: vi.fn(), plan: vi.fn() },
  verificationApi: { status: vi.fn(), createSession: vi.fn() },
  journeyApi: { today: vi.fn() },
  notifyApi: { track: vi.fn().mockResolvedValue(undefined) },
  apiDetail: () => "",
  apiStatus: () => null,
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(notifyApi.track).mockResolvedValue(undefined);
  vi.mocked(onboardingApi.get).mockResolvedValue({
    experience: "", play_frequency: "", fide_rating: null, lichess_username: "",
    chesscom_username: "", goal: "", intensity: "standard", timezone: "Asia/Tehran",
    onboarding_completed: false, placement_completed: false,
  });
});

describe("onboarding flow", () => {
  it("walks four short steps and saves", async () => {
    const user = userEvent.setup();
    vi.mocked(onboardingApi.save).mockResolvedValue({
      experience: "beginner", play_frequency: "weekly", fide_rating: null, lichess_username: "",
      chesscom_username: "", goal: "improve", intensity: "standard", timezone: "Asia/Tehran",
      onboarding_completed: true, placement_completed: false,
    });
    vi.mocked(onboardingApi.plan).mockResolvedValue({
      onboarding_completed: true, placement_completed: false, intensity: "standard",
      goal_text: "تقویت قدم‌به‌قدم مهارت‌ها", focus_exercise: "captures",
      headline: "مسیر پیشنهادی تو", summary: "از تمرین‌های کوتاه شروع می‌کنیم.",
    });
    vi.mocked(onboardingApi.placement).mockResolvedValue([]);
    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "مبتدی‌ام" }));
    await user.click(screen.getByRole("button", { name: "ادامه" }));
    await user.click(screen.getByRole("button", { name: "هفته‌ای چند بار" }));
    await user.click(screen.getByRole("button", { name: "ادامه" }));
    // Optional step skips without blocking.
    await user.click(screen.getByRole("button", { name: "رد کردن" }));
    await user.click(screen.getByRole("button", { name: "قوی‌تر شدن" }));
    await user.click(screen.getByRole("button", { name: "ساختن مسیر من" }));
    await waitFor(() => expect(onboardingApi.save).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("مسیر پیشنهادی تو")).toBeTruthy());
  });

  it("validates required steps before continuing", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: "ادامه" }).hasAttribute("disabled")).toBe(true);
    await user.click(screen.getByRole("button", { name: "تازه شروع کردم" }));
    expect(screen.getByRole("button", { name: "ادامه" }).hasAttribute("disabled")).toBe(false);
  });
});

describe("channel verification", () => {
  it("offers Telegram/Bale, shows the pairing code, no phone typing", async () => {
    const user = userEvent.setup();
    vi.mocked(verificationApi.createSession).mockResolvedValue({
      channel: "telegram", pairing_code: "123456", bot_username: "testbot",
      bot_url: "https://t.me/testbot", expires_at: "",
    });
    render(
      <MemoryRouter>
        <VerifyPage />
      </MemoryRouter>,
    );
    expect(screen.queryByPlaceholderText(/09/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "تأیید با تلگرام" }));
    await waitFor(() => expect(verificationApi.createSession).toHaveBeenCalledWith("telegram"));
    await waitFor(() => expect(screen.getByText("123456")).toBeTruthy());
  });

  it("shows the success state with premium CTA after verification", async () => {
    const user = userEvent.setup();
    vi.mocked(verificationApi.createSession).mockResolvedValue({
      channel: "bale", pairing_code: "654321", bot_username: "", bot_url: "",
      expires_at: "",
    });
    vi.mocked(verificationApi.status).mockResolvedValue({
      verified: true, phone_masked: "+98912***6789", channel: "bale",
    });
    render(
      <MemoryRouter>
        <VerifyPage />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "تأیید با بله" }));
    await waitFor(() => expect(screen.getByText("شماره‌ات تأیید شد")).toBeTruthy());
    expect(screen.getByRole("button", { name: "دریافت حساب ویژه" })).toBeTruthy();
  });
});
