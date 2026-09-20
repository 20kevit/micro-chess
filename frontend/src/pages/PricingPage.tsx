import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { billingApi } from "../api/client";
import type { BillingPlan, CouponQuote, Entitlements, Subscription } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";
import { faNum } from "../lib/playerDisplay";

const FREE_FEATURES = [
  "basic_training",
  "practice_access",
  "progress_tracking",
  "recommendations",
  "basic_xp_streak",
  "coach_features",
  "parent_features",
];

const PREMIUM_FEATURES = [
  ...FREE_FEATURES,
  "advanced_analytics",
  "advanced_personalization",
  "personalized_training_package",
  "speed_training",
  "premium_training_content",
];

function featureLabel(key: string): string {
  return t(`pricing.feature.${key}` as FaKey);
}

function formatDate(value: string | null): string {
  if (!value) return "";
  try {
    return new Date(value).toLocaleDateString("fa-IR");
  } catch {
    return value;
  }
}

// Public pricing page. Prices, discounts, and access all come from the
// server; nothing here is authoritative. Paid checkout does not exist
// yet, so the premium CTA is an honest "coming soon".
export function PricingPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[] | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [code, setCode] = useState("");
  const [quote, setQuote] = useState<CouponQuote | null>(null);
  const [couponError, setCouponError] = useState<string | null>(null);
  const [couponOk, setCouponOk] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let alive = true;
    billingApi
      .plans()
      .then((rows) => {
        if (alive) setPlans(rows);
      })
      .catch(() => {
        if (alive) setPlans([]);
      });
    if (user) {
      billingApi
        .subscription()
        .then((s) => {
          if (alive) setSubscription(s);
        })
        .catch(() => {});
      billingApi
        .entitlements()
        .then((e) => {
          if (alive) setEntitlements(e);
        })
        .catch(() => {});
    } else {
      setSubscription(null);
      setEntitlements(null);
    }
    return () => {
      alive = false;
    };
  }, [user]);

  async function onValidate(e: FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setWorking(true);
    setCouponError(null);
    setCouponOk(null);
    setQuote(null);
    try {
      const q = await billingApi.validateCoupon({ code: code.trim() });
      setQuote(q);
    } catch {
      setCouponError(t("coupon.invalid"));
    } finally {
      setWorking(false);
    }
  }

  async function onRedeem() {
    if (!quote) return;
    setWorking(true);
    setCouponError(null);
    setCouponOk(null);
    try {
      const r = await billingApi.redeemCoupon({ code: quote.code });
      if (quote.discount_type === "free_trial") {
        setCouponOk(t("coupon.applied"));
      } else {
        setCouponOk(t("coupon.pendingNote"));
      }
      void r;
      const s = await billingApi.subscription();
      setSubscription(s);
      const ent = await billingApi.entitlements();
      setEntitlements(ent);
    } catch (err) {
      const detail =
        err instanceof Error && "detail" in err
          ? String((err as { detail: string }).detail)
          : "";
      if (detail === "coupon_expired") setCouponError(t("coupon.expired"));
      else if (
        detail === "max_redemptions_exhausted" ||
        detail === "per_user_limit" ||
        detail === "trial_already_used"
      )
        setCouponError(t("coupon.limit"));
      else setCouponError(t("coupon.invalid"));
    } finally {
      setWorking(false);
    }
  }

  const free = (plans ?? []).find((p) => p.code === "free");
  const premium = (plans ?? []).find((p) => p.code === "premium");

  return (
    <div>
      <PageHeader title={t("pricing.title")} subtitle={t("pricing.subtitle")} />
      {user && subscription ? (
        <Card>
          <p className="text-sm font-bold text-stone-700">
            {t("pricing.currentPlan")}:{" "}
            {subscription.plan_code === "premium"
              ? t("account.plan.premium")
              : t("account.plan.free")}{" "}
            ({t(`pricing.status.${subscription.status}` as FaKey)})
          </p>
          {subscription.status === "trialing" && subscription.trial_ends_at ? (
            <p className="mt-1 text-sm text-stone-500">
              {t("account.trialUntil")}: {formatDate(subscription.trial_ends_at)}
            </p>
          ) : null}
          {entitlements && !entitlements.has_paid_access ? (
            <p className="mt-1 text-sm text-stone-500">{t("pricing.trialNote")}</p>
          ) : null}
        </Card>
      ) : null}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-xl font-black text-stone-900">
            {free?.name_fa ?? t("pricing.freeName")}
          </h2>
          <p className="mt-1 text-sm text-stone-500">{t("pricing.subtitle")}</p>
          <ul className="mt-3 flex flex-col gap-2">
            {FREE_FEATURES.map((f) => (
              <li key={f} className="text-sm font-bold text-stone-700">
                ✓ {featureLabel(f)}
              </li>
            ))}
          </ul>
          <Link to="/register" className="mt-4 block">
            <Button className="w-full">{t("pricing.freeCta")}</Button>
          </Link>
        </Card>
        <Card>
          <h2 className="text-xl font-black text-stone-900">
            {premium?.name_fa ?? t("pricing.premiumName")}
          </h2>
          <p className="mt-1 text-sm text-stone-500">{premium?.description_fa}</p>
          <ul className="mt-3 flex flex-col gap-2">
            {PREMIUM_FEATURES.map((f) => (
              <li key={f} className="text-sm font-bold text-stone-700">
                ✓ {featureLabel(f)}
              </li>
            ))}
          </ul>
          <Button className="mt-4 w-full" disabled>
            {t("pricing.soon")}
          </Button>
          <p className="mt-2 text-xs leading-6 text-stone-500">{t("pricing.soonNote")}</p>
        </Card>
      </div>
      {user ? (
        <Card>
          <h2 className="text-lg font-black text-stone-900">{t("coupon.title")}</h2>
          <form onSubmit={onValidate} className="mt-3 flex flex-col gap-2">
            <input
              dir="ltr"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={t("coupon.placeholder")}
              className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-center text-base"
            />
            <Button type="submit" variant="secondary" disabled={working || !code.trim()}>
              {working ? t("common.loading") : t("coupon.apply")}
            </Button>
          </form>
          {couponError ? (
            <p role="alert" className="mt-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
              {couponError}
            </p>
          ) : null}
          {couponOk ? (
            <p role="status" className="mt-2 rounded-2xl bg-green-50 px-4 py-3 text-sm font-bold text-green-700">
              {couponOk}
            </p>
          ) : null}
          {quote ? (
            <div className="mt-3 rounded-2xl bg-violet-50 px-4 py-3">
              <p dir="ltr" className="text-center text-lg font-black text-violet-700">
                {quote.code}
              </p>
              {quote.trial_days > 0 ? (
                <p className="mt-1 text-center text-sm font-bold text-stone-700">
                  {faNum(quote.trial_days)} {t("coupon.trialDays")}
                </p>
              ) : null}
              {quote.discount_minor > 0 ? (
                <p className="mt-1 text-center text-sm font-bold text-stone-700">
                  {t("coupon.discount")}: {faNum(quote.discount_minor)}
                </p>
              ) : null}
              <Button className="mt-3 w-full" disabled={working} onClick={() => void onRedeem()}>
                {t("coupon.redeem")}
              </Button>
            </div>
          ) : null}
        </Card>
      ) : (
        <Card>
          <p className="text-center text-sm text-stone-500">{t("pricing.trialNote")}</p>
          <Link to="/register" className="mt-3 block">
            <Button variant="secondary" className="w-full">
              {t("pricing.freeCta")}
            </Button>
          </Link>
        </Card>
      )}
    </div>
  );
}
