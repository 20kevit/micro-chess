import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiDetail, notifyApi, premiumApi, verificationApi } from "../api/client";
import type { PremiumQuote, VerificationStatus } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

// Premium activation: verified phone + coupon invoice + zero-amount
// settlement. No gateway exists in this phase, so a payable above zero
// is honestly refused instead of redirecting anywhere. All math and
// decisions are server-side; this page only renders quotes and posts
// the coupon code.
export function PremiumPage() {
  const navigate = useNavigate();
  const [verification, setVerification] = useState<VerificationStatus | null>(null);
  const [code, setCode] = useState("");
  const [quote, setQuote] = useState<PremiumQuote | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [working, setWorking] = useState(false);
  const [activated, setActivated] = useState(false);

  const loadVerification = useCallback(() => {
    verificationApi
      .status()
      .then(setVerification)
      .catch(() => setVerification(null));
  }, []);

  useEffect(() => {
    loadVerification();
    notifyApi.track("premium_upgrade_started").catch(() => {});
  }, [loadVerification]);

  function describe(e: unknown): string {
    const detail = apiDetail(e);
    if (detail === "phone_not_verified") return t("premium.needVerification");
    if (detail === "coupon_not_found" || detail === "coupon_invalid") return t("coupon.invalid");
    if (detail === "coupon_expired") return t("coupon.expired");
    if (
      detail === "max_redemptions_exhausted" ||
      detail === "per_user_limit" ||
      detail === "trial_already_used" ||
      detail === "first_time_only"
    )
      return t("coupon.limit");
    if (detail === "payment_required") return t("premium.paymentRequired");
    return t("common.error");
  }

  async function onQuote(e: FormEvent) {
    e.preventDefault();
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const q = await premiumApi.quote(code.trim() || undefined);
      setQuote(q);
      if (code.trim()) notifyApi.track("coupon_entered").catch(() => {});
    } catch (err) {
      setError(describe(err));
      setQuote(null);
    } finally {
      setWorking(false);
    }
  }

  async function onActivate() {
    if (!quote?.coupon_code) return;
    setWorking(true);
    setError("");
    try {
      const out = await premiumApi.activate(quote.coupon_code);
      void out;
      setActivated(true);
      notifyApi.track("coupon_redeemed").catch(() => {});
    } catch (err) {
      setError(describe(err));
    } finally {
      setWorking(false);
    }
  }

  if (activated) {
    return (
      <div>
        <PageHeader title={t("premium.successTitle")} subtitle={t("premium.successHint")} />
        <Card>
          <p className="text-center text-5xl" aria-hidden>
            🎉
          </p>
          <div className="mt-3 flex flex-col gap-2">
            <Button onClick={() => navigate("/")}>{t("journey.goQuests")}</Button>
            <Link to="/account" className="block">
              <Button variant="secondary" className="w-full">
                {t("nav.account")}
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("premium.title")} subtitle={t("premium.subtitle")} />
      <Card>
        <ul className="flex flex-col gap-2 text-sm font-bold text-stone-700">
          <li>✓ {t("premium.benefit.quota")}</li>
          <li>✓ {t("premium.benefit.journey")}</li>
          <li>✓ {t("premium.benefit.progress")}</li>
        </ul>
      </Card>

      {verification !== null && !verification.verified ? (
        <Card>
          <p className="text-sm font-bold text-stone-700">{t("premium.verifyFirst")}</p>
          <p className="mt-1 text-sm text-stone-500">{t("verify.subtitle")}</p>
          <Link to="/verify" className="mt-3 block">
            <Button className="w-full">{t("premium.goVerify")}</Button>
          </Link>
        </Card>
      ) : null}

      <Card>
        <h2 className="font-black">{t("premium.invoiceTitle")}</h2>
        <form onSubmit={onQuote} className="mt-3 flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
            {t("premium.coupon")}
            <input
              dir="ltr"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={t("coupon.placeholder")}
              autoComplete="off"
              className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-center text-base font-normal"
            />
          </label>
          <Button type="submit" variant="secondary" disabled={working}>
            {working ? t("common.loading") : t("premium.showInvoice")}
          </Button>
        </form>
        {quote ? (
          <div className="mt-3 rounded-2xl bg-violet-50 px-4 py-3">
            <dl className="flex flex-col gap-1 text-sm font-bold text-stone-700">
              <div className="flex items-center justify-between gap-2">
                <dt>{t("premium.price")}</dt>
                <dd>
                  {faNum(quote.price_amount_minor)} {t("premium.toman")}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt>{t("premium.discount")}</dt>
                <dd>
                  {faNum(quote.discount_minor)} {t("premium.toman")}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2 border-t border-violet-200 pt-1 text-base text-violet-800">
                <dt>{t("premium.payable")}</dt>
                <dd>
                  {faNum(quote.final_amount_minor)} {t("premium.toman")}
                </dd>
              </div>
            </dl>
            {quote.coupon_code && quote.final_amount_minor === 0 ? (
              <Button className="mt-3 w-full" disabled={working} onClick={() => void onActivate()}>
                {t("premium.activate")}
              </Button>
            ) : null}
            {quote.gateway_required ? (
              <p className="mt-2 text-sm text-stone-500">{t("premium.paymentRequired")}</p>
            ) : null}
          </div>
        ) : null}
        {error ? (
          <p role="alert" className="mt-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
            {error}
          </p>
        ) : null}
        {notice ? <p className="mt-2 text-sm font-bold text-violet-700">{notice}</p> : null}
      </Card>
    </div>
  );
}
