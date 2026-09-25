import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PremiumPage } from "./PremiumPage";
import { premiumApi, verificationApi, notifyApi } from "../api/client";

vi.mock("../api/client", () => ({
  premiumApi: { quote: vi.fn(), activate: vi.fn() },
  verificationApi: { status: vi.fn() },
  notifyApi: { track: vi.fn().mockResolvedValue(undefined) },
  apiDetail: (e: unknown) =>
    e instanceof Error && "detail" in e ? String((e as { detail: string }).detail) : "",
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(notifyApi.track).mockResolvedValue(undefined);
  vi.mocked(verificationApi.status).mockResolvedValue({
     verified: true, phone_masked: "+98912***6789", channel: "telegram", available_channels: ["telegram", "bale"],
  });
});

function quoteOf(final: number, code = "PREM100") {
  return {
    plan_code: "premium", plan_name_fa: "حرفه‌ای", price_amount_minor: 990000,
    currency: "IRR", discount_minor: 990000 - final, final_amount_minor: final,
    coupon_code: code, gateway_required: final > 0,
  };
}

describe("premium activation", () => {
  it("asks verification first when the phone is unverified", async () => {
    vi.mocked(verificationApi.status).mockResolvedValue({
       verified: false, phone_masked: "", channel: null, available_channels: ["bale"],
    });
    render(
      <MemoryRouter>
        <PremiumPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("اول شماره‌ات را تأیید کن.")).toBeTruthy());
    expect(screen.getByRole("link", { name: "احراز شماره تلفن" }).getAttribute("href")).toBe("/verify");
  });

  it("shows a zero-payable invoice and activates without gateway", async () => {
    const user = userEvent.setup();
    vi.mocked(premiumApi.quote).mockResolvedValue(quoteOf(0));
    vi.mocked(premiumApi.activate).mockResolvedValue({
      subscription_id: 7, plan_code: "premium", status: "active",
      final_amount_minor: 0, already: false,
    });
    render(
      <MemoryRouter>
        <PremiumPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("مثلاً ABADEH1405"), "PREM100");
    await user.click(screen.getByRole("button", { name: "دیدن فاکتور" }));
    await waitFor(() => expect(screen.getByText("قابل پرداخت")).toBeTruthy());
    await user.click(screen.getByRole("button", { name: "فعال‌سازی حساب ویژه" }));
    await waitFor(() => expect(premiumApi.activate).toHaveBeenCalledWith("PREM100"));
    await waitFor(() => expect(screen.getByText("حساب ویژه فعال شد")).toBeTruthy());
    expect(screen.getByText("از امروز می‌توانی تا ۱۰۰ تمرین در روز انجام دهی.")).toBeTruthy();
  });

  it("refuses nonzero payables honestly instead of a gateway redirect", async () => {
    const user = userEvent.setup();
    vi.mocked(premiumApi.quote).mockResolvedValue(quoteOf(495000));
    render(
      <MemoryRouter>
        <PremiumPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("مثلاً ABADEH1405"), "HALF50");
    await user.click(screen.getByRole("button", { name: "دیدن فاکتور" }));
    await waitFor(() =>
      expect(screen.getByText("برای این مبلغ پرداخت اینترنتی لازم است که فعلاً فعال نیست.")).toBeTruthy(),
    );
    expect(screen.queryByRole("button", { name: "فعال‌سازی حساب ویژه" })).toBeNull();
  });

  it("maps coupon errors to Persian messages", async () => {
    const user = userEvent.setup();
    vi.mocked(premiumApi.quote).mockRejectedValue(Object.assign(new Error("x"), { detail: "coupon_expired" }));
    render(
      <MemoryRouter>
        <PremiumPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText("مثلاً ABADEH1405"), "OLD");
    await user.click(screen.getByRole("button", { name: "دیدن فاکتور" }));
    await waitFor(() => expect(screen.getByText("مهلت این کد تمام شده است.")).toBeTruthy());
  });
});
