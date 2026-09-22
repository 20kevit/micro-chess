import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingPage } from "./OnboardingPage";
import { VerifyPhonePage } from "./VerifyPhonePage";
import { onboardingApi, phoneApi, notifyApi } from "../api/client";

vi.mock("../api/client", () => ({
  onboardingApi: { get: vi.fn(), save: vi.fn(), placement: vi.fn(), completePlacement: vi.fn(), plan: vi.fn() },
  phoneApi: { status: vi.fn(), start: vi.fn(), resend: vi.fn(), verify: vi.fn() },
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

describe("phone verification", () => {
  it("sends an OTP then verifies the code", async () => {
    const user = userEvent.setup();
    vi.mocked(phoneApi.status).mockResolvedValue({ phone: null, verified: false });
    vi.mocked(phoneApi.start).mockResolvedValue({ phone: "+98912", expires_at: "", sent: true });
    vi.mocked(phoneApi.verify).mockResolvedValue({ phone: "+98912", verified: true });
    render(
      <MemoryRouter>
        <VerifyPhonePage />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("مثلاً 09123456789"), "09123456789");
    await user.click(screen.getByRole("button", { name: "ارسال کد تأیید" }));
    await waitFor(() => expect(phoneApi.start).toHaveBeenCalled());
    await user.type(await screen.findByLabelText(/کد تأیید/), "123456");
    await user.click(screen.getByRole("button", { name: "تأیید" }));
    await waitFor(() => expect(phoneApi.verify).toHaveBeenCalledWith("123456"));
  });

  it("accepts only digits in the OTP field", async () => {
    const user = userEvent.setup();
    vi.mocked(phoneApi.status).mockResolvedValue({ phone: null, verified: false });
    vi.mocked(phoneApi.start).mockResolvedValue({ phone: "+98912", expires_at: "", sent: true });
    render(
      <MemoryRouter>
        <VerifyPhonePage />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("مثلاً 09123456789"), "09123456789");
    await user.click(screen.getByRole("button", { name: "ارسال کد تأیید" }));
    const code = await screen.findByLabelText(/کد تأیید/);
    await user.type(code, "12ab34");
    expect((code as HTMLInputElement).value).toBe("1234");
  });
});
