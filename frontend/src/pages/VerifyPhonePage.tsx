import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiDetail, apiStatus, phoneApi } from "../api/client";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Phone verification: number entry -> OTP code entry -> verified.
// Accessible OTP input (one field, numeric, autocomplete), Persian UX,
// clear states for cooldown/invalid/expired without leaking the code.
export function VerifyPhonePage() {
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    phoneApi
      .status()
      .then((s) => {
        setVerified(s.verified);
        if (s.phone) {
          setSentTo(s.phone);
          setPhone((prev) => prev || s.phone || "");
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (verified) navigate("/onboarding", { replace: true });
  }, [verified, navigate]);

  function describe(e: unknown): string {
    const detail = apiDetail(e);
    if (detail === "resend_cooldown") return t("phone.error.cooldown");
    if (detail === "code_expired") return t("phone.error.expired");
    if (detail === "code_invalid") return t("phone.error.invalid");
    if (detail === "phone_taken") return t("phone.error.taken");
    if (detail === "phone_invalid") return t("phone.number");
    if (apiStatus(e) === 429) return t("auth.error.rateLimited");
    return t("common.error");
  }

  async function onStart(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const out = await phoneApi.start(phone.trim());
      setSentTo(out.phone);
      if (!out.sent) setError(t("phone.notSent"));
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const out = await phoneApi.verify(code.trim());
      if (out.verified) {
        setVerified(true);
        navigate("/onboarding", { replace: true });
      }
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setBusy(true);
    setError("");
    try {
      await phoneApi.resend();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("phone.title")} subtitle={t("phone.subtitle")} />
      <Card>
        {!sentTo ? (
          <form onSubmit={onStart} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
              {t("phone.number")}
              <input
                dir="ltr"
                inputMode="tel"
                autoComplete="tel"
                placeholder={t("phone.numberPlaceholder")}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
              />
            </label>
            {error ? (
              <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {error}
              </p>
            ) : null}
            <Button type="submit" disabled={busy || !phone.trim()}>
              {busy ? t("common.loading") : t("phone.sendCode")}
            </Button>
          </form>
        ) : (
          <form onSubmit={onVerify} className="flex flex-col gap-3">
            <p className="text-sm text-stone-500" dir="ltr">
              {sentTo}
            </p>
            <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
              {t("phone.code")}
              <input
                dir="ltr"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                aria-describedby="otp-hint"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
                className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-center text-2xl font-black tracking-[0.5em]"
              />
              <span id="otp-hint" className="text-xs font-normal text-stone-500">
                {t("phone.codeHint")}
              </span>
            </label>
            {error ? (
              <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {error}
              </p>
            ) : null}
            <Button type="submit" disabled={busy || code.length !== 6}>
              {busy ? t("common.loading") : t("phone.verify")}
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={onResend} disabled={busy} className="flex-1">
                {t("phone.resend")}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setSentTo(null);
                  setCode("");
                }}
                disabled={busy}
                className="flex-1"
              >
                {t("phone.changeNumber")}
              </Button>
            </div>
          </form>
        )}
        <Link
          to="/onboarding"
          className="mt-3 flex min-h-[44px] items-center justify-center font-bold text-violet-700"
        >
          {t("phone.skip")}
        </Link>
      </Card>
    </div>
  );
}
