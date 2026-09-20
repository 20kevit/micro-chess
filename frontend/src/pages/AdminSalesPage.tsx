import { useEffect, useState } from "react";
import { adminApi, adminBillingApi, apiDetail } from "../api/client";
import type {
  AdminCoupon,
  AdminPlan,
  CampaignReport,
  Redemption,
  SalesOverview,
  Subscription,
} from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

type Tab = "overview" | "plans" | "coupons" | "campaigns" | "subscriptions" | "payments";

const TABS: Array<[Tab, string]> = [
  ["overview", "admin.dashboard"],
  ["plans", "admin.plans"],
  ["coupons", "admin.coupons"],
  ["campaigns", "admin.campaigns"],
  ["subscriptions", "admin.subscriptions"],
  ["payments", "admin.payments"],
];

function inputClass(): string {
  return "min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm";
}

export function AdminSalesPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [sales, setSales] = useState<SalesOverview | null>(null);
  const [report, setReport] = useState<CampaignReport[]>([]);
  const [plans, setPlans] = useState<AdminPlan[] | null>(null);
  const [coupons, setCoupons] = useState<AdminCoupon[] | null>(null);
  const [campaigns, setCampaigns] = useState<Array<{ slug: string; name_fa: string; source: string; medium: string; content: string; is_active: boolean }> | null>(null);
  const [subs, setSubs] = useState<Array<Subscription & { user_id: number }> | null>(null);
  const [payments, setPayments] = useState<Array<Record<string, unknown>> | null>(null);
  const [redemptions, setRedemptions] = useState<Redemption[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [subStatus, setSubStatus] = useState("");
  const [payStatus, setPayStatus] = useState("");
  const [redemptionCoupon, setRedemptionCoupon] = useState("");
  const [detailCoupon, setDetailCoupon] = useState<AdminCoupon | null>(null);
  // Create forms.
  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [pricePlan, setPricePlan] = useState("");
  const [priceAmount, setPriceAmount] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [couponType, setCouponType] = useState("percent");
  const [couponValue, setCouponValue] = useState("10");
  const [couponTrial, setCouponTrial] = useState("0");
  const [couponCampaign, setCouponCampaign] = useState("");
  const [couponPlans, setCouponPlans] = useState("");
  const [campaignSlug, setCampaignSlug] = useState("");
  const [campaignName, setCampaignName] = useState("");

  const loadOverview = () => {
    setLoading(true);
    setFailed(false);
    Promise.all([adminApi.salesOverview(), adminBillingApi.report()])
      .then(([s, r]) => {
        setSales(s);
        setReport(r);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  };

  useEffect(loadOverview, []);

  const loadTab = (next: Tab) => {
    setTab(next);
    setNotice("");
    if (next === "plans" && plans === null) {
      adminBillingApi.plans().then(setPlans).catch(() => setNotice(t("common.error")));
    }
    if (next === "coupons" && coupons === null) {
      adminBillingApi.coupons().then(setCoupons).catch(() => setNotice(t("common.error")));
    }
    if (next === "campaigns" && campaigns === null) {
      adminBillingApi.campaigns().then(setCampaigns).catch(() => setNotice(t("common.error")));
    }
    if (next === "subscriptions") {
      adminBillingApi
        .subscriptions({ status: subStatus || undefined, page_size: 50 })
        .then(setSubs)
        .catch(() => setNotice(t("common.error")));
    }
    if (next === "payments") {
      adminBillingApi
        .payments({ status: payStatus || undefined, page_size: 50 })
        .then(setPayments)
        .catch(() => setNotice(t("common.error")));
    }
  };

  const refreshPlans = () => adminBillingApi.plans().then(setPlans);
  const refreshCoupons = () => adminBillingApi.coupons().then(setCoupons);
  const refreshCampaigns = () => adminBillingApi.campaigns().then(setCampaigns);

  async function act(fn: () => Promise<unknown>, refresh?: () => Promise<unknown>) {
    setBusy(true);
    setNotice("");
    try {
      await fn();
      if (refresh) await refresh();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function confirmToggle(): boolean {
    return window.confirm(t("admin.toggleConfirm"));
  }

  async function onCreatePlan() {
    if (!planCode.trim() || !planName.trim()) {
      setNotice(t("common.error"));
      return;
    }
    await act(
      () => adminBillingApi.createPlan({ code: planCode.trim(), name_fa: planName.trim() }),
      refreshPlans,
    );
    setPlanCode("");
    setPlanName("");
  }

  async function onCreatePrice() {
    const amount = Number(priceAmount);
    if (!pricePlan.trim() || !Number.isInteger(amount) || amount < 0) {
      setNotice(t("common.error"));
      return;
    }
    await act(
      () => adminBillingApi.createPrice(pricePlan.trim(), { amount_minor: amount }),
      refreshPlans,
    );
    setPriceAmount("");
  }

  async function onCreateCoupon() {
    if (!couponCode.trim()) {
      setNotice(t("common.error"));
      return;
    }
    await act(
      () =>
        adminBillingApi.createCoupon({
          code: couponCode.trim(),
          discount_type: couponType,
          discount_value: Number(couponValue) || 0,
          trial_days: Number(couponTrial) || 0,
          campaign_slug: couponCampaign.trim() || undefined,
          applicable_plan_codes: couponPlans
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      refreshCoupons,
    );
    setCouponCode("");
  }

  async function onCreateCampaign() {
    if (!campaignSlug.trim()) {
      setNotice(t("common.error"));
      return;
    }
    await act(
      () =>
        adminBillingApi.createCampaign({ slug: campaignSlug.trim(), name_fa: campaignName.trim() }),
      refreshCampaigns,
    );
    setCampaignSlug("");
    setCampaignName("");
  }

  async function openCouponDetail(coupon: AdminCoupon) {
    setDetailCoupon(coupon);
    setRedemptions(null);
    try {
      const rows = await adminBillingApi.redemptions({ coupon_code: coupon.code, page_size: 50 });
      setRedemptions(rows);
    } catch {
      setNotice(t("common.error"));
    }
  }

  return (
    <AdminLayout>
      <PageHeader title={t("admin.sales")} subtitle={t("admin.salesSubtitle")} />
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
        {TABS.map(([value, key]) => (
          <button
            key={value}
            type="button"
            onClick={() => void loadTab(value)}
            className={`min-h-[44px] shrink-0 rounded-full px-4 text-sm font-bold ${
              tab === value ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"
            }`}
          >
            {t(key as never)}
          </button>
        ))}
      </div>
      {notice ? <p className="mb-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}

      {tab === "overview" ? (
        loading ? (
          <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
        ) : failed || !sales ? (
          <div className="py-8 text-center">
            <p className="text-stone-500">{t("common.error")}</p>
            <Button onClick={loadOverview} className="mx-auto mt-3 max-w-xs">
              {t("common.retry")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
              <Card className="text-center">
                <p className="text-2xl font-black text-violet-700">{faNum(sales.revenue_minor)}</p>
                <p className="mt-1 text-xs text-stone-500">{t("admin.revenue")}</p>
              </Card>
              <Card className="text-center">
                <p className="text-2xl font-black text-violet-700">{faNum(sales.redemptions_total)}</p>
                <p className="mt-1 text-xs text-stone-500">{t("admin.redemptions")}</p>
              </Card>
            </div>
            <Card>
              <h2 className="font-black">{t("admin.subscriptions")}</h2>
              <ul className="mt-2 flex flex-col gap-1">
                {sales.subscriptions_by_status.map((row) => (
                  <li key={row.status} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                    <span dir="ltr" className="font-bold">{row.status}</span>
                    <span>{faNum(row.count)}</span>
                  </li>
                ))}
                {sales.subscriptions_by_status.length === 0 && <p className="text-sm text-stone-500">{t("admin.empty")}</p>}
              </ul>
            </Card>
            <Card>
              <h2 className="font-black">{t("admin.payments")}</h2>
              <ul className="mt-2 flex flex-col gap-1">
                {sales.payments_by_status.map((row) => (
                  <li key={row.status} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                    <span dir="ltr" className="font-bold">{row.status}</span>
                    <span>{faNum(row.count)}</span>
                  </li>
                ))}
                {sales.payments_by_status.length === 0 && <p className="text-sm text-stone-500">{t("admin.empty")}</p>}
              </ul>
            </Card>
          </div>
        )
      ) : null}

      {tab === "plans" ? (
        <div className="flex flex-col gap-2">
          <Card>
            <h2 className="font-black">{t("admin.createPlan")}</h2>
            <div className="mt-2 flex flex-col gap-2">
              <input value={planCode} onChange={(e) => setPlanCode(e.target.value)} placeholder={t("admin.planCode")} dir="ltr" className={inputClass()} />
              <input value={planName} onChange={(e) => setPlanName(e.target.value)} placeholder={t("admin.planName")} className={inputClass()} />
              <Button disabled={busy} onClick={() => void onCreatePlan()}>{t("admin.createPlan")}</Button>
            </div>
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.createPrice")}</h2>
            <div className="mt-2 flex flex-col gap-2">
              <input value={pricePlan} onChange={(e) => setPricePlan(e.target.value)} placeholder={t("admin.planCode")} dir="ltr" className={inputClass()} />
              <input value={priceAmount} onChange={(e) => setPriceAmount(e.target.value)} placeholder={t("admin.priceAmount")} dir="ltr" inputMode="numeric" className={inputClass()} />
              <Button disabled={busy} onClick={() => void onCreatePrice()}>{t("admin.createPrice")}</Button>
            </div>
          </Card>
          {plans === null ? (
            <p className="py-4 text-center text-stone-500">{t("common.loading")}</p>
          ) : plans.length === 0 ? (
            <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            plans.map((plan) => (
              <Card key={plan.code}>
                <div className="flex min-h-[44px] items-center justify-between gap-2">
                  <span className="font-black">{plan.name_fa} <span dir="ltr" className="text-xs text-stone-400">{plan.code}</span></span>
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      if (!confirmToggle()) return;
                      void act(() => adminBillingApi.setPlanActive(plan.code, !plan.is_active), refreshPlans);
                    }}
                  >
                    {plan.is_active ? t("admin.deactivate") : t("admin.activate")}
                  </Button>
                </div>
                <h3 className="mt-2 text-sm font-bold text-stone-500">{t("admin.priceHistory")}</h3>
                {plan.prices.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-1 flex flex-col gap-1">
                    {plan.prices.map((price) => (
                      <li key={price.id} className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-1">
                        <span dir="ltr" className="text-sm">
                          v{faNum(price.version)} · {faNum(price.amount_minor)} {price.currency}
                          {!price.is_active ? ` · ${t("admin.statusRetired")}` : ""}
                        </span>
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => {
                            if (!confirmToggle()) return;
                            void act(() => adminBillingApi.setPriceActive(price.id, !price.is_active), refreshPlans);
                          }}
                        >
                          {price.is_active ? t("admin.deactivate") : t("admin.activate")}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            ))
          )}
        </div>
      ) : null}

      {tab === "coupons" ? (
        <div className="flex flex-col gap-2">
          <Card>
            <h2 className="font-black">{t("admin.createCoupon")}</h2>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input value={couponCode} onChange={(e) => setCouponCode(e.target.value)} placeholder={t("admin.couponCode")} dir="ltr" className={inputClass()} />
              <select value={couponType} onChange={(e) => setCouponType(e.target.value)} className={inputClass()} dir="ltr">
                <option value="percent">percent</option>
                <option value="fixed">fixed</option>
                <option value="free_trial">free_trial</option>
              </select>
              <input value={couponValue} onChange={(e) => setCouponValue(e.target.value)} placeholder={t("admin.discountValue")} dir="ltr" inputMode="numeric" className={inputClass()} />
              <input value={couponTrial} onChange={(e) => setCouponTrial(e.target.value)} placeholder={t("admin.trialDays")} dir="ltr" inputMode="numeric" className={inputClass()} />
              <input value={couponCampaign} onChange={(e) => setCouponCampaign(e.target.value)} placeholder={t("admin.campaignSlug")} dir="ltr" className={inputClass()} />
              <input value={couponPlans} onChange={(e) => setCouponPlans(e.target.value)} placeholder={t("admin.applicablePlans")} dir="ltr" className={inputClass()} />
            </div>
            <div className="mt-2">
              <Button disabled={busy} onClick={() => void onCreateCoupon()} className="w-full">{t("admin.createCoupon")}</Button>
            </div>
          </Card>
          {coupons === null ? (
            <p className="py-4 text-center text-stone-500">{t("common.loading")}</p>
          ) : coupons.length === 0 ? (
            <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            coupons.map((coupon) => (
              <Card key={coupon.id}>
                <div className="flex min-h-[44px] items-center justify-between gap-2">
                  <button type="button" onClick={() => void openCouponDetail(coupon)} className="font-black" dir="ltr">
                    {coupon.code}
                  </button>
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      if (!confirmToggle()) return;
                      void act(() => adminBillingApi.setCouponActive(coupon.id, !coupon.is_active), refreshCoupons);
                    }}
                  >
                    {coupon.is_active ? t("admin.deactivate") : t("admin.activate")}
                  </Button>
                </div>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.discountType")}: <span dir="ltr">{coupon.discount_type} {coupon.discount_value}</span> ·{" "}
                  {t("admin.trialDays")}: {faNum(coupon.trial_days)} · {t("admin.redemptions")}:{" "}
                  {faNum(coupon.total_redemptions)}
                  {coupon.max_redemptions ? `/${faNum(coupon.max_redemptions)}` : ""} · {t("admin.maxPerUser")}:{" "}
                  {faNum(coupon.max_per_user)}
                  {coupon.valid_until ? ` · ${t("admin.validUntil")}: ${coupon.valid_until}` : ""} ·{" "}
                  {t("admin.applicablePlans")}:{" "}
                  <span dir="ltr">
                    {coupon.applicable_plan_codes.length ? coupon.applicable_plan_codes.join(", ") : t("admin.all")}
                  </span>
                </p>
                {detailCoupon?.id === coupon.id ? (
                  <div className="mt-2">
                    <h3 className="text-sm font-bold">{t("admin.couponDetail")}</h3>
                    {redemptions === null ? (
                      <p className="text-sm text-stone-500">{t("common.loading")}</p>
                    ) : redemptions.length === 0 ? (
                      <p className="text-sm text-stone-500">{t("admin.empty")}</p>
                    ) : (
                      <ul className="mt-1 flex flex-col gap-1">
                        {redemptions.map((r) => (
                    <li key={r.id} className="rounded-xl bg-stone-50 px-3 py-2 text-xs">
                      #{faNum(r.id)} · {t("admin.userLabel")} {r.subscription_id ?? "?"} ·{" "}
                      <span dir="ltr">{r.status}</span> · {t("admin.discountValue")}:{" "}
                      {faNum(r.discount_granted_minor)} · {t("admin.trialDays")}: {faNum(r.trial_days_granted)}
                    </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </Card>
            ))
          )}
        </div>
      ) : null}

      {tab === "campaigns" ? (
        <div className="flex flex-col gap-2">
          <Card>
            <h2 className="font-black">{t("admin.createCampaign")}</h2>
            <div className="mt-2 flex flex-col gap-2">
              <input value={campaignSlug} onChange={(e) => setCampaignSlug(e.target.value)} placeholder={t("admin.campaignSlug")} dir="ltr" className={inputClass()} />
              <input value={campaignName} onChange={(e) => setCampaignName(e.target.value)} placeholder={t("admin.campaignName")} className={inputClass()} />
              <Button disabled={busy} onClick={() => void onCreateCampaign()}>{t("admin.createCampaign")}</Button>
            </div>
          </Card>
          {campaigns === null ? (
            <p className="py-4 text-center text-stone-500">{t("common.loading")}</p>
          ) : campaigns.length === 0 ? (
            <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            campaigns.map((campaign) => {
              const stats = report.find((r) => r.slug === campaign.slug);
              return (
                <Card key={campaign.slug}>
                  <div className="flex min-h-[44px] items-center justify-between gap-2">
                    <span className="font-black" dir="ltr">{campaign.slug}</span>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => {
                        if (!confirmToggle()) return;
                        void act(() => adminBillingApi.setCampaignActive(campaign.slug, !campaign.is_active), refreshCampaigns);
                      }}
                    >
                      {campaign.is_active ? t("admin.deactivate") : t("admin.activate")}
                    </Button>
                  </div>
                  <p className="mt-1 text-sm text-stone-500">{campaign.name_fa}</p>
                  {stats ? (
                    <p className="mt-1 text-xs text-stone-500">
                      {t("admin.newRegistrations")}: {faNum(stats.registrations)} · {t("admin.redemptions")}:{" "}
                      {faNum(stats.redemptions)} · {t("admin.trials")}: {faNum(stats.trials)} ·{" "}
                      {t("admin.paidUsers")}: {faNum(stats.paid)}
                    </p>
                  ) : null}
                </Card>
              );
            })
          )}
        </div>
      ) : null}

      {tab === "subscriptions" ? (
        <div className="flex flex-col gap-2">
          <Card>
            <p className="text-xs text-stone-500">{t("admin.readOnlyNote")}</p>
            <div className="mt-2 flex gap-2">
              <select value={subStatus} onChange={(e) => { setSubStatus(e.target.value); }} className={inputClass()} dir="ltr">
                <option value="">{t("admin.all")}</option>
                <option value="pending">pending</option>
                <option value="trialing">trialing</option>
                <option value="active">active</option>
                <option value="expired">expired</option>
                <option value="cancelled">cancelled</option>
                <option value="past_due">past_due</option>
              </select>
              <Button variant="secondary" disabled={busy} onClick={() => loadTab("subscriptions")}>{t("common.retry")}</Button>
            </div>
          </Card>
          {subs === null ? (
            <p className="py-4 text-center text-stone-500">{t("common.loading")}</p>
          ) : subs.length === 0 ? (
            <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            subs.map((sub) => (
              <Card key={sub.id}>
                <p className="font-bold">
                  #{faNum(sub.id)} · {t("admin.userLabel")} {faNum(sub.user_id)} ·{" "}
                  <span dir="ltr">{sub.plan_code} · {sub.status}</span>
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.sourceLabel")}: <span dir="ltr">{sub.source}</span> · {t("admin.trialDays")}:{" "}
                  <span dir="ltr">{sub.trial_ends_at ?? "—"}</span> · {t("admin.periodLabel")}:{" "}
                  <span dir="ltr">{sub.current_period_start ?? "—"} → {sub.current_period_end ?? "—"}</span> ·{" "}
                  {t("admin.couponCode")}: <span dir="ltr">{sub.coupon_code ?? "—"}</span>
                </p>
              </Card>
            ))
          )}
        </div>
      ) : null}

      {tab === "payments" ? (
        <div className="flex flex-col gap-2">
          <Card>
            <p className="text-xs text-stone-500">{t("admin.readOnlyNote")}</p>
            <div className="mt-2 flex gap-2">
              <select value={payStatus} onChange={(e) => { setPayStatus(e.target.value); }} className={inputClass()} dir="ltr">
                <option value="">{t("admin.all")}</option>
                <option value="pending">pending</option>
                <option value="requires_action">requires_action</option>
                <option value="verified">verified</option>
                <option value="failed">failed</option>
                <option value="cancelled">cancelled</option>
              </select>
              <Button variant="secondary" disabled={busy} onClick={() => loadTab("payments")}>{t("common.retry")}</Button>
            </div>
          </Card>
          {payments === null ? (
            <p className="py-4 text-center text-stone-500">{t("common.loading")}</p>
          ) : payments.length === 0 ? (
            <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            payments.map((row) => (
              <Card key={String(row["id"])}>
                <p className="font-bold">
                  #{String(row["id"])} · {t("admin.userLabel")} {String(row["user_id"])} ·{" "}
                  {faNum(Number(row["final_amount_minor"]))} <span dir="ltr">{String(row["currency"])}</span> ·{" "}
                  <span dir="ltr">{String(row["status"])}</span>
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.providerLabel")}: <span dir="ltr">{String(row["provider"])}</span> ·{" "}
                  {t("admin.refLabel")}: <span dir="ltr">{String(row["provider_ref"] ?? "—")}</span> ·{" "}
                  {t("admin.subscriptions")}: <span dir="ltr">{String(row["subscription_id"] ?? "—")}</span> ·{" "}
                  {t("admin.couponCode")}: <span dir="ltr">{String(row["coupon_code"] ?? "—")}</span>
                </p>
                {row["failure_reason"] ? (
                  <p className="mt-1 text-xs font-bold text-red-600" dir="ltr">{String(row["failure_reason"])}</p>
                ) : null}
              </Card>
            ))
          )}
          <Card>
            <h2 className="font-black">{t("admin.redemptions")}</h2>
            <div className="mt-2 flex gap-2">
              <input value={redemptionCoupon} onChange={(e) => setRedemptionCoupon(e.target.value)} placeholder={t("admin.couponCode")} dir="ltr" className={inputClass()} />
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  adminBillingApi
                    .redemptions({ coupon_code: redemptionCoupon.trim() || undefined, page_size: 50 })
                    .then(setRedemptions)
                    .catch(() => setNotice(t("common.error")))
                    .finally(() => setBusy(false));
                }}
              >
                {t("admin.details")}
              </Button>
            </div>
            {redemptions !== null && (
              redemptions.length === 0 ? (
                <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
              ) : (
                <ul className="mt-2 flex flex-col gap-1">
                  {redemptions.map((r) => (
                    <li key={r.id} className="rounded-xl bg-stone-50 px-3 py-2 text-xs">
                      #{faNum(r.id)} <span dir="ltr">{r.coupon_code} · {r.status}</span> ·{" "}
                      {t("admin.discountValue")}: {faNum(r.discount_granted_minor)}
                    </li>
                  ))}
                </ul>
              )
            )}
          </Card>
        </div>
      ) : null}
    </AdminLayout>
  );
}
