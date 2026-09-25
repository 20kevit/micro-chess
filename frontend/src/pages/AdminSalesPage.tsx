import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi, adminBillingApi } from "../api/client";
import type { PageResult } from "../api/client";
import type { FaKey } from "../i18n/fa";
import type {
  AdminCampaign,
  AdminCoupon,
  AdminPayment,
  AdminPlan,
  AdminRedemption,
  AdminSubscription,
  CampaignReport,
  SalesOverview,
} from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import {
  adminSourceLabel,
  adminStatusLabel,
  billingIntervalLabel,
  couponTypeLabel,
  faDate,
  faDateTime,
  faNum,
} from "../lib/playerDisplay";

type Tab = "overview" | "plans" | "coupons" | "campaigns" | "subscriptions" | "payments";
type PageValue<T> = PageResult<T> | T[];

const TABS: Array<[Tab, FaKey]> = [
  ["overview", "admin.dashboard"],
  ["plans", "admin.plans"],
  ["coupons", "admin.coupons"],
  ["campaigns", "admin.campaigns"],
  ["subscriptions", "admin.subscriptions"],
  ["payments", "admin.payments"],
];
const SUB_PAGE_SIZE = 20;
const REDEMPTION_PAGE_SIZE = 20;
const INTERVALS = ["monthly", "yearly", "lifetime", "none"] as const;
const COUPON_TYPES = ["percent", "fixed", "free_trial"] as const;

function tabFrom(value: string | null): Tab {
  return TABS.some(([tab]) => tab === value) ? value as Tab : "overview";
}

function unpack<T>(value: PageValue<T>): { items: T[]; total: number } {
  if (Array.isArray(value)) return { items: value, total: value.length };
  return value;
}

function inputClass(): string {
  return "min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm";
}

function pageSummary(page: number, total: number, size: number): string {
  const pages = Math.max(1, Math.ceil(total / size));
  return t("admin.pagination.summary")
    .replace("{page}", faNum(page))
    .replace("{pages}", faNum(pages))
    .replace("{total}", faNum(total));
}

function optionalInt(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : undefined;
}

function money(amount: number | null | undefined, currency: string | null | undefined): string {
  return `${faNum(amount ?? 0)} ${currency || "IRR"}`;
}

function paymentProviderLabel(provider: string): string {
  return provider && provider !== "none" ? t("admin.providerLabel") : t("admin.health.notConnected");
}

function couponState(coupon: AdminCoupon): string {
  if (!coupon.is_active) return t("admin.statusDisabled");
  const now = Date.now();
  if (coupon.valid_from && new Date(coupon.valid_from).getTime() > now) return t("admin.status.pending");
  if (coupon.valid_until && new Date(coupon.valid_until).getTime() < now) return t("admin.status.expired");
  return t("admin.statusActive");
}

function redemptionStatusLabel(status: string): string {
  if (status === "applied") return t("admin.status.verified");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "pending") return t("admin.status.pending");
  return adminStatusLabel(status);
}

function reportValue(value: number): string {
  return faNum(value);
}

export function AdminSalesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => tabFrom(searchParams.get("tab")));
  const [sales, setSales] = useState<SalesOverview | null>(null);
  const [report, setReport] = useState<CampaignReport[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewFailed, setOverviewFailed] = useState(false);
  const [plans, setPlans] = useState<AdminPlan[] | null>(null);
  const [coupons, setCoupons] = useState<AdminCoupon[] | null>(null);
  const [campaigns, setCampaigns] = useState<AdminCampaign[] | null>(null);
  const [subscriptions, setSubscriptions] = useState<AdminSubscription[] | null>(null);
  const [subscriptionTotal, setSubscriptionTotal] = useState(0);
  const [payments, setPayments] = useState<AdminPayment[] | null>(null);
  const [paymentTotal, setPaymentTotal] = useState(0);
  const [redemptions, setRedemptions] = useState<AdminRedemption[] | null>(null);
  const [redemptionTotal, setRedemptionTotal] = useState(0);
  const [redemptionPage, setRedemptionPage] = useState(1);
  const [selectedCoupon, setSelectedCoupon] = useState<AdminCoupon | null>(null);
  const [subStatus, setSubStatus] = useState("");
  const [subPage, setSubPage] = useState(1);
  const [payStatus, setPayStatus] = useState("");
  const [payPage, setPayPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [planDescription, setPlanDescription] = useState("");
  const [planInterval, setPlanInterval] = useState("monthly");
  const [planSortOrder, setPlanSortOrder] = useState("0");
  const [pricePlan, setPricePlan] = useState("");
  const [priceAmount, setPriceAmount] = useState("");
  const [priceCurrency, setPriceCurrency] = useState("IRR");
  const [priceInterval, setPriceInterval] = useState("monthly");
  const [couponCode, setCouponCode] = useState("");
  const [couponType, setCouponType] = useState("percent");
  const [couponValue, setCouponValue] = useState("0");
  const [couponTrial, setCouponTrial] = useState("0");
  const [couponDescription, setCouponDescription] = useState("");
  const [couponCurrency, setCouponCurrency] = useState("IRR");
  const [couponCampaign, setCouponCampaign] = useState("");
  const [couponFrom, setCouponFrom] = useState("");
  const [couponUntil, setCouponUntil] = useState("");
  const [couponMax, setCouponMax] = useState("");
  const [couponPerUser, setCouponPerUser] = useState("1");
  const [couponMinimum, setCouponMinimum] = useState("0");
  const [couponFirstTime, setCouponFirstTime] = useState(false);
  const [couponActive, setCouponActive] = useState(true);
  const [couponPlans, setCouponPlans] = useState<string[]>([]);
  const [campaignSlug, setCampaignSlug] = useState("");
  const [campaignName, setCampaignName] = useState("");
  const [campaignSource, setCampaignSource] = useState("");
  const [campaignMedium, setCampaignMedium] = useState("");
  const [campaignContent, setCampaignContent] = useState("");

  useEffect(() => {
    setTab(tabFrom(searchParams.get("tab")));
  }, [searchParams]);

  const loadOverview = useCallback(() => {
    let alive = true;
    setOverviewLoading(true);
    setOverviewFailed(false);
    const reportRequest = typeof adminBillingApi.report === "function"
      ? adminBillingApi.report()
      : Promise.resolve([] as CampaignReport[]);
    const salesRequest = typeof adminApi.salesOverview === "function"
      ? adminApi.salesOverview()
      : Promise.reject(new Error("sales overview unavailable"));
    Promise.all([salesRequest, reportRequest])
      .then(([overview, attribution]) => {
        if (!alive) return;
        setSales(overview);
        setReport(attribution);
      })
      .catch(() => {
        if (alive) setOverviewFailed(true);
      })
      .finally(() => {
        if (alive) setOverviewLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    return loadOverview();
  }, [loadOverview]);

  const refreshPlans = async () => {
    if (typeof adminBillingApi.plans !== "function") {
      setPlans([]);
      return;
    }
    const rows = await adminBillingApi.plans();
    setPlans(rows);
  };
  const refreshCoupons = async () => {
    if (typeof adminBillingApi.coupons !== "function") {
      setCoupons([]);
      return;
    }
    const rows = await adminBillingApi.coupons();
    setCoupons(rows);
  };
  const refreshCampaigns = async () => {
    if (typeof adminBillingApi.campaigns !== "function") {
      setCampaigns([]);
      return;
    }
    const rows = await adminBillingApi.campaigns();
    setCampaigns(rows);
  };

  useEffect(() => {
    if (tab !== "plans" && tab !== "coupons") return;
    if (plans !== null) return;
    void refreshPlans().catch(() => setNotice(t("common.error")));
  }, [plans, tab]);

  useEffect(() => {
    if (tab !== "campaigns" && tab !== "coupons") return;
    if (campaigns !== null) return;
    void refreshCampaigns().catch(() => setNotice(t("common.error")));
  }, [campaigns, tab]);

  useEffect(() => {
    if (tab !== "coupons" || coupons !== null) return;
    void refreshCoupons().catch(() => setNotice(t("common.error")));
  }, [coupons, tab]);

  useEffect(() => {
    if (tab !== "subscriptions") return;
    let alive = true;
    const params = { status: subStatus || undefined, page: subPage, page_size: SUB_PAGE_SIZE };
    const request = typeof adminBillingApi.subscriptionsPage === "function"
      ? adminBillingApi.subscriptionsPage(params)
      : typeof adminBillingApi.subscriptions === "function"
        ? adminBillingApi.subscriptions(params).then((rows) => ({ items: rows, total: rows.length }))
        : Promise.resolve({ items: [], total: 0 });
    request
      .then((response) => {
        if (!alive) return;
        const result = unpack(response as PageValue<AdminSubscription>);
        setSubscriptions(result.items);
        setSubscriptionTotal(result.total);
      })
      .catch(() => setNotice(t("common.error")));
    return () => {
      alive = false;
    };
  }, [subPage, subStatus, tab]);

  useEffect(() => {
    if (tab !== "payments") return;
    let alive = true;
    const params = { status: payStatus || undefined, page: payPage, page_size: SUB_PAGE_SIZE };
    const request = typeof adminBillingApi.paymentsPage === "function"
      ? adminBillingApi.paymentsPage(params)
      : typeof adminBillingApi.payments === "function"
        ? adminBillingApi.payments(params).then((rows) => ({ items: rows, total: rows.length }))
        : Promise.resolve({ items: [], total: 0 });
    request
      .then((response) => {
        if (!alive) return;
        const result = unpack(response as PageValue<AdminPayment>);
        setPayments(result.items);
        setPaymentTotal(result.total);
      })
      .catch(() => setNotice(t("common.error")));
    return () => {
      alive = false;
    };
  }, [payPage, payStatus, tab]);

  function selectTab(next: Tab) {
    setTab(next);
    setNotice("");
    setSearchParams(next === "overview" ? {} : { tab: next });
  }

  async function act(action: () => Promise<unknown>, refresh?: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setNotice("");
    try {
      await action();
      if (refresh) await refresh();
      return true;
    } catch {
      setNotice(t("common.error"));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function createPlan() {
    if (!planCode.trim() || !planName.trim()) {
      setNotice(t("common.error"));
      return;
    }
    const success = await act(
      () => adminBillingApi.createPlan({
        code: planCode.trim(),
        name_fa: planName.trim(),
        description_fa: planDescription.trim(),
        billing_interval: planInterval,
        sort_order: Number(planSortOrder) || 0,
      }),
      refreshPlans,
    );
    if (success) {
      setPlanCode("");
      setPlanName("");
      setPlanDescription("");
      setPlanSortOrder("0");
    }
  }

  async function createPrice() {
    const amount = optionalInt(priceAmount);
    if (!pricePlan || amount === undefined || amount < 0) {
      setNotice(t("common.error"));
      return;
    }
    const success = await act(
      () => adminBillingApi.createPrice(pricePlan, {
        amount_minor: amount,
        currency: priceCurrency.trim() || "IRR",
        billing_interval: priceInterval,
      }),
      refreshPlans,
    );
    if (success) {
      setPriceAmount("");
      setPricePlan("");
    }
  }

  async function createCoupon() {
    if (!couponCode.trim()) {
      setNotice(t("common.error"));
      return;
    }
    const payload: Record<string, unknown> = {
      code: couponCode.trim(),
      discount_type: couponType,
      discount_value: Number(couponValue) || 0,
      trial_days: Number(couponTrial) || 0,
      description: couponDescription.trim(),
      currency: couponCurrency.trim() || "IRR",
      valid_from: couponFrom || undefined,
      valid_until: couponUntil || undefined,
      max_redemptions: optionalInt(couponMax),
      max_per_user: Number(couponPerUser) || 0,
      first_time_only: couponFirstTime,
      min_amount_minor: Number(couponMinimum) || 0,
      applicable_plan_codes: couponPlans,
    };
    if (couponCampaign) payload.campaign_slug = couponCampaign;
    const success = await act(async () => {
      const created = await adminBillingApi.createCoupon(payload);
      if (!couponActive && created && typeof created.id === "number") {
        await adminBillingApi.setCouponActive(created.id, false);
      }
    }, refreshCoupons);
    if (success) {
      setCouponCode("");
      setCouponValue("0");
      setCouponTrial("0");
      setCouponDescription("");
      setCouponFrom("");
      setCouponUntil("");
      setCouponMax("");
      setCouponPerUser("1");
      setCouponMinimum("0");
      setCouponFirstTime(false);
      setCouponActive(true);
      setCouponPlans([]);
      setCouponCampaign("");
    }
  }

  async function createCampaign() {
    if (!campaignSlug.trim()) {
      setNotice(t("common.error"));
      return;
    }
    const success = await act(
      () => adminBillingApi.createCampaign({
        slug: campaignSlug.trim(),
        name_fa: campaignName.trim(),
        source: campaignSource.trim(),
        medium: campaignMedium.trim(),
        content: campaignContent.trim(),
      }),
      refreshCampaigns,
    );
    if (success) {
      setCampaignSlug("");
      setCampaignName("");
      setCampaignSource("");
      setCampaignMedium("");
      setCampaignContent("");
    }
  }

  async function loadRedemptions(coupon: AdminCoupon, page = 1) {
    setSelectedCoupon(coupon);
    setRedemptionPage(page);
    setRedemptions(null);
    const params = { coupon_code: coupon.code, page, page_size: REDEMPTION_PAGE_SIZE };
    try {
      const response = typeof adminBillingApi.redemptionsPage === "function"
        ? await adminBillingApi.redemptionsPage(params)
        : typeof adminBillingApi.redemptions === "function"
          ? await adminBillingApi.redemptions(params)
          : { items: [], total: 0 };
      const result = unpack(response as PageValue<AdminRedemption>);
      setRedemptions(result.items);
      setRedemptionTotal(result.total);
    } catch {
      setNotice(t("common.error"));
    }
  }

  const activePlans = useMemo(() => (plans ?? []).filter((plan) => plan.is_active), [plans]);


  return (
    <div>
      <PageHeader title={t("admin.sales")} subtitle={t("admin.salesSubtitle")} />
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label={t("admin.sales")}>
        {TABS.map(([value, key]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => selectTab(value)}
            className={`min-h-[44px] shrink-0 rounded-full px-4 text-sm font-bold ${tab === value ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"}`}
          >
             {t(key)}
          </button>
        ))}
      </div>
      {notice ? <p className="mb-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}

      {tab === "overview" ? (
        overviewLoading ? <p className="py-8 text-center text-stone-500">{t("common.loading")}</p> : overviewFailed || !sales ? (
          <div className="py-8 text-center"><p className="text-stone-500">{t("common.error")}</p><div className="mx-auto mt-3 max-w-xs"><Button onClick={() => void loadOverview()}>{t("common.retry")}</Button></div></div>
        ) : (
          <div className="flex flex-col gap-3">
            <Card>
              <p className="text-sm text-stone-600">{t("admin.sales.overviewNote")}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                <Card><p className="text-2xl font-black text-violet-700" dir="ltr">{money(sales.revenue_minor, sales.revenue_currency)}</p><p className="mt-1 text-xs text-stone-500">{t("admin.revenue")}</p></Card>
                <Card><p className="text-2xl font-black text-violet-700">{faNum(sales.redemptions_total)}</p><p className="mt-1 text-xs text-stone-500">{t("admin.redemptions")}</p></Card>
                <Card><p className="text-2xl font-black text-violet-700">{faNum(sales.subscriptions_by_status.reduce((sum, row) => sum + row.count, 0))}</p><p className="mt-1 text-xs text-stone-500">{t("admin.subscriptions")}</p></Card>
                <Card><p className="text-2xl font-black text-violet-700">{faNum(sales.payments_by_status.reduce((sum, row) => sum + row.count, 0))}</p><p className="mt-1 text-xs text-stone-500">{t("admin.payments")}</p></Card>
              </div>
            </Card>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Card><h2 className="font-black">{t("admin.subscriptions")}</h2>{sales.subscriptions_by_status.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <ul className="mt-2 flex flex-col gap-1">{sales.subscriptions_by_status.map((row) => <li key={row.status} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"><span>{adminStatusLabel(row.status)}</span><span className="font-bold">{faNum(row.count)}</span></li>)}</ul>}</Card>
              <Card><h2 className="font-black">{t("admin.payments")}</h2>{sales.payments_by_status.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <ul className="mt-2 flex flex-col gap-1">{sales.payments_by_status.map((row) => <li key={row.status} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"><span>{adminStatusLabel(row.status)}</span><span className="font-bold">{faNum(row.count)}</span></li>)}</ul>}</Card>
            </div>
            <Card><h2 className="font-black">{t("admin.attributionOverview")}</h2>{report.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[720px] text-right text-sm"><thead className="text-xs text-stone-500"><tr><th className="p-2">{t("admin.label.campaign")}</th><th className="p-2">{t("admin.campaign.users")}</th><th className="p-2">{t("admin.redemptions")}</th><th className="p-2">{t("admin.trials")}</th><th className="p-2">{t("admin.paidUsers")}</th></tr></thead><tbody>{report.map((row) => <tr key={row.slug} className="border-t border-stone-100"><td className="p-2 font-bold" dir="ltr">{row.slug}</td><td className="p-2">{reportValue(row.registrations)}</td><td className="p-2">{reportValue(row.redemptions)}</td><td className="p-2">{reportValue(row.trials)}</td><td className="p-2">{reportValue(row.paid)}</td></tr>)}</tbody></table></div>}<p className="mt-3 text-xs text-stone-500">{t("admin.sales.conversionNote")}</p></Card>
            <Card><p className="text-sm text-stone-600">{t("admin.payment.deferred")}</p></Card>
          </div>
        )
      ) : null}

      {tab === "plans" ? (
        <div className="flex flex-col gap-3">
          <Card><h2 className="font-black">{t("admin.plans.purpose")}</h2><form className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); void createPlan(); }}><label className="text-sm font-bold">{t("admin.planCode")}<input value={planCode} onChange={(event) => setPlanCode(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.planName")}<input value={planName} onChange={(event) => setPlanName(event.target.value)} className={`${inputClass()} mt-1`} /></label><label className="text-sm font-bold md:col-span-2">{t("admin.plans.description")}<textarea value={planDescription} onChange={(event) => setPlanDescription(event.target.value)} className="mt-1 min-h-[88px] w-full rounded-xl border border-stone-200 p-3 text-sm" /></label><label className="text-sm font-bold">{t("admin.plans.interval")}<select value={planInterval} onChange={(event) => setPlanInterval(event.target.value)} className={`${inputClass()} mt-1`}>{INTERVALS.map((value) => <option key={value} value={value}>{billingIntervalLabel(value)}</option>)}</select></label><label className="text-sm font-bold">{t("admin.sortBy")}<input value={planSortOrder} onChange={(event) => setPlanSortOrder(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} /></label><Button type="submit" disabled={busy} className="md:col-span-2">{t("admin.createPlan")}</Button></form></Card>
          <Card><h2 className="font-black">{t("admin.createPrice")}</h2><p className="mt-1 text-xs text-stone-500">{t("admin.plans.priceVersionNote")}</p><form className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); void createPrice(); }}><label className="text-sm font-bold">{t("admin.plans.select")}<select value={pricePlan} onChange={(event) => setPricePlan(event.target.value)} className={`${inputClass()} mt-1`}><option value="">{t("admin.all")}</option>{activePlans.map((plan) => <option key={plan.code} value={plan.code}>{plan.name_fa} ({plan.code})</option>)}</select></label><label className="text-sm font-bold">{t("admin.priceAmount")}<input value={priceAmount} onChange={(event) => setPriceAmount(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.currency")}<input value={priceCurrency} onChange={(event) => setPriceCurrency(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.plans.interval")}<select value={priceInterval} onChange={(event) => setPriceInterval(event.target.value)} className={`${inputClass()} mt-1`}>{INTERVALS.map((value) => <option key={value} value={value}>{billingIntervalLabel(value)}</option>)}</select></label><Button type="submit" disabled={busy} className="md:col-span-2">{t("admin.createPrice")}</Button></form></Card>
          {plans === null ? <p className="py-4 text-center text-stone-500">{t("common.loading")}</p> : plans.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <div className="flex flex-col gap-3">{plans.map((plan) => <Card key={plan.code}><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-black">{plan.name_fa}</h2><p className="text-xs text-stone-500" dir="ltr">{plan.code} · {billingIntervalLabel(plan.billing_interval)}</p></div><div className="flex items-center gap-2"><Badge>{plan.is_active ? t("admin.statusActive") : t("admin.statusDisabled")}</Badge><Button variant="secondary" disabled={busy} onClick={() => { if (window.confirm(t("admin.toggleConfirm"))) void act(() => adminBillingApi.setPlanActive(plan.code, !plan.is_active), refreshPlans); }}>{plan.is_active ? t("admin.deactivate") : t("admin.activate")}</Button></div></div><p className="mt-2 text-sm text-stone-600">{plan.description_fa || t("admin.empty")}</p><h3 className="mt-2 text-sm font-black">{t("admin.priceHistory")}</h3><p className="mt-1 text-xs text-stone-500">{t("admin.plans.priceVersionNote")}</p><div className="mt-2 flex flex-col gap-1">{plan.prices.length === 0 ? <p className="text-sm text-stone-500">{t("admin.empty")}</p> : plan.prices.map((price) => <div key={price.id} className="flex min-h-[44px] flex-wrap items-center justify-between gap-2 rounded-xl bg-stone-50 px-3"><span dir="ltr">{t("admin.version")} {faNum(price.version)} · {money(price.amount_minor, price.currency)} · {billingIntervalLabel(price.billing_interval)}</span><span className="flex items-center gap-2"><Badge>{adminStatusLabel(price.is_active ? "active" : "retired")}</Badge><Button variant="ghost" disabled={busy} onClick={() => { if (window.confirm(t("admin.toggleConfirm"))) void act(() => adminBillingApi.setPriceActive(price.id, !price.is_active), refreshPlans); }}>{price.is_active ? t("admin.deactivate") : t("admin.activate")}</Button></span></div>)}</div></Card>)}</div>}
        </div>
      ) : null}

      {tab === "coupons" ? (
        <div className="flex flex-col gap-3">
          <Card><h2 className="font-black">{t("admin.createCoupon")}</h2><form className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); void createCoupon(); }}><label className="text-sm font-bold">{t("admin.couponCode")}<input value={couponCode} onChange={(event) => setCouponCode(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.coupon.type")}<select value={couponType} onChange={(event) => setCouponType(event.target.value)} className={`${inputClass()} mt-1`}>{COUPON_TYPES.map((value) => <option key={value} value={value}>{value === "free_trial" ? `${t("admin.coupon.freeAccess")} (${t("admin.coupon.freeTrial")})` : couponTypeLabel(value)}</option>)}</select></label><label className="text-sm font-bold">{t("admin.discountValue")}<input value={couponValue} onChange={(event) => setCouponValue(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.trialDays")}<input value={couponTrial} onChange={(event) => setCouponTrial(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold md:col-span-2">{t("admin.coupon.description")}<input value={couponDescription} onChange={(event) => setCouponDescription(event.target.value)} className={`${inputClass()} mt-1`} /></label><label className="text-sm font-bold">{t("admin.coupon.relatedCampaign")}<select value={couponCampaign} onChange={(event) => setCouponCampaign(event.target.value)} className={`${inputClass()} mt-1`}><option value="">{t("admin.all")}</option>{(campaigns ?? []).map((campaign) => <option key={campaign.slug} value={campaign.slug}>{campaign.name_fa} ({campaign.slug})</option>)}</select></label><label className="text-sm font-bold">{t("admin.currency")}<input value={couponCurrency} onChange={(event) => setCouponCurrency(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.coupon.start")}<input value={couponFrom} onChange={(event) => setCouponFrom(event.target.value)} type="date" className={`${inputClass()} mt-1`} /></label><label className="text-sm font-bold">{t("admin.coupon.expiry")}<input value={couponUntil} onChange={(event) => setCouponUntil(event.target.value)} type="date" className={`${inputClass()} mt-1`} /></label><label className="text-sm font-bold">{t("admin.coupon.usageLimit")}<input value={couponMax} onChange={(event) => setCouponMax(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.coupon.perUserLimit")}<input value={couponPerUser} onChange={(event) => setCouponPerUser(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.coupon.minimumAmount")}<input value={couponMinimum} onChange={(event) => setCouponMinimum(event.target.value)} type="number" min="0" className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="flex min-h-[44px] items-center gap-2 text-sm font-bold"><input type="checkbox" checked={couponFirstTime} onChange={(event) => setCouponFirstTime(event.target.checked)} />{t("admin.coupon.firstTimeOnly")}</label><label className="flex min-h-[44px] items-center gap-2 text-sm font-bold"><input type="checkbox" checked={couponActive} onChange={(event) => setCouponActive(event.target.checked)} />{t("admin.filterActive")}</label><label className="text-sm font-bold md:col-span-2">{t("admin.coupon.selectPlans")}<select multiple value={couponPlans} onChange={(event) => setCouponPlans(Array.from(event.target.selectedOptions, (option) => option.value))} className={`${inputClass()} mt-1 min-h-[120px]`}>{activePlans.map((plan) => <option key={plan.code} value={plan.code}>{plan.name_fa} ({plan.code})</option>)}</select></label><Button type="submit" disabled={busy} className="md:col-span-2">{t("admin.createCoupon")}</Button></form></Card>
          {coupons === null ? <p className="py-4 text-center text-stone-500">{t("common.loading")}</p> : coupons.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <div className="flex flex-col gap-3">{coupons.map((coupon) => <Card key={coupon.id}><div className="flex flex-wrap items-center justify-between gap-2"><button type="button" className="font-black text-violet-700" dir="ltr" onClick={() => void loadRedemptions(coupon)}>{coupon.code}</button><div className="flex items-center gap-2"><Badge>{couponState(coupon)}</Badge><Button variant="secondary" disabled={busy} onClick={() => { if (window.confirm(t("admin.toggleConfirm"))) void act(() => adminBillingApi.setCouponActive(coupon.id, !coupon.is_active), refreshCoupons); }}>{coupon.is_active ? t("admin.deactivate") : t("admin.activate")}</Button></div></div><p className="mt-2 text-sm">{coupon.description || t("admin.empty")}</p><div className="mt-2 grid grid-cols-2 gap-2 text-xs text-stone-500 md:grid-cols-4"><span>{t("admin.coupon.type")}: {couponTypeLabel(coupon.discount_type)}</span><span>{t("admin.discountValue")}: {coupon.discount_type === "percent" ? `${faNum(coupon.discount_value)}٪` : money(coupon.discount_value, coupon.currency)}</span><span>{t("admin.trialDays")}: {faNum(coupon.trial_days)}</span><span>{t("admin.maxRedemptions")}: {coupon.max_redemptions === null ? t("admin.coupon.unlimited") : faNum(coupon.max_redemptions)}</span><span>{t("admin.coupon.remaining")}: {coupon.max_redemptions === null ? t("admin.coupon.unlimited") : faNum(Math.max(0, coupon.max_redemptions - coupon.total_redemptions))}</span><span>{t("admin.maxPerUser")}: {faNum(coupon.max_per_user)}</span><span>{t("admin.coupon.firstTimeOnly")}: {coupon.first_time_only ? t("admin.yes") : t("admin.no")}</span><span>{t("admin.coupon.minimumAmount")}: {money(coupon.min_amount_minor, coupon.currency)}</span><span>{t("admin.coupon.start")}: {coupon.valid_from ? <span dir="ltr">{faDate(coupon.valid_from)}</span> : t("admin.notAvailable")}</span><span>{t("admin.coupon.expiry")}: {coupon.valid_until ? <span dir="ltr">{faDate(coupon.valid_until)}</span> : t("admin.notAvailable")}</span><span>{t("admin.coupon.relatedCampaign")}: <span dir="ltr">{coupon.campaign_slug || t("admin.notAvailable")}</span></span><span className="col-span-2">{t("admin.coupon.selectPlans")}: <span dir="ltr">{coupon.applicable_plan_codes.length ? coupon.applicable_plan_codes.join("، ") : t("admin.coupon.allPlans")}</span></span></div>{selectedCoupon?.id === coupon.id ? <div className="mt-3 border-t border-stone-100 pt-3"><div className="flex items-center justify-between gap-2"><h3 className="font-black">{t("admin.couponDetail")}</h3><span className="text-xs text-stone-500">{pageSummary(redemptionPage, redemptionTotal, REDEMPTION_PAGE_SIZE)}</span></div>{redemptions === null ? <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p> : redemptions.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <ul className="mt-2 flex flex-col gap-1">{redemptions.map((redemption) => <li key={redemption.id} className="rounded-xl bg-stone-50 px-3 py-2 text-xs"><Link to={`/admin/users/${redemption.user_id}`} className="font-bold text-violet-700">{t("admin.label.user")} {faNum(redemption.user_id)}</Link><p className="mt-1 text-stone-500">{redemptionStatusLabel(redemption.status)} · {t("admin.discountValue")}: {faNum(redemption.discount_granted_minor)} · {t("admin.trialDays")}: {faNum(redemption.trial_days_granted)}</p><p className="mt-1 text-stone-500" dir="ltr">{faDateTime(redemption.created_at)}</p></li>)}</ul>}<div className="mt-2 flex justify-between gap-2"><Button variant="secondary" disabled={redemptionPage <= 1} onClick={() => void loadRedemptions(coupon, redemptionPage - 1)}>{t("admin.pagination.previous")}</Button><Button variant="secondary" disabled={redemptionPage >= Math.max(1, Math.ceil(redemptionTotal / REDEMPTION_PAGE_SIZE))} onClick={() => void loadRedemptions(coupon, redemptionPage + 1)}>{t("admin.pagination.next")}</Button></div></div> : null}</Card>)}</div>}
        </div>
      ) : null}

      {tab === "campaigns" ? (
        <div className="flex flex-col gap-3"><Card><h2 className="font-black">{t("admin.campaign.purpose")}</h2><form className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); void createCampaign(); }}><label className="text-sm font-bold">{t("admin.campaignSlug")}<input value={campaignSlug} onChange={(event) => setCampaignSlug(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.campaignName")}<input value={campaignName} onChange={(event) => setCampaignName(event.target.value)} className={`${inputClass()} mt-1`} /></label><label className="text-sm font-bold">{t("admin.campaign.source")}<input value={campaignSource} onChange={(event) => setCampaignSource(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold">{t("admin.campaign.medium")}<input value={campaignMedium} onChange={(event) => setCampaignMedium(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><label className="text-sm font-bold md:col-span-2">{t("admin.campaign.content")}<input value={campaignContent} onChange={(event) => setCampaignContent(event.target.value)} className={`${inputClass()} mt-1`} dir="ltr" /></label><Button type="submit" disabled={busy} className="md:col-span-2">{t("admin.createCampaign")}</Button></form></Card>{campaigns === null ? <p className="py-4 text-center text-stone-500">{t("common.loading")}</p> : campaigns.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <div className="flex flex-col gap-3">{campaigns.map((campaign) => { const stats = report.find((row) => row.slug === campaign.slug); return <Card key={campaign.slug}><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-black" dir="ltr">{campaign.slug}</h2><p className="text-sm text-stone-500">{campaign.name_fa}</p></div><Button variant="secondary" disabled={busy} onClick={() => { if (window.confirm(t("admin.toggleConfirm"))) void act(() => adminBillingApi.setCampaignActive(campaign.slug, !campaign.is_active), refreshCampaigns); }}>{campaign.is_active ? t("admin.deactivate") : t("admin.activate")}</Button></div><div className="mt-2 grid grid-cols-2 gap-2 text-xs text-stone-500 md:grid-cols-4"><span>{t("admin.campaign.source")}: <span dir="ltr">{campaign.source || t("admin.notAvailable")}</span></span><span>{t("admin.campaign.medium")}: <span dir="ltr">{campaign.medium || t("admin.notAvailable")}</span></span><span>{t("admin.campaign.content")}: <span dir="ltr">{campaign.content || t("admin.notAvailable")}</span></span><span>{t("admin.label.status")}: {campaign.is_active ? t("admin.statusActive") : t("admin.statusDisabled")}</span></div><div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4"><div className="rounded-xl bg-stone-50 p-2"><p className="text-xs text-stone-500">{t("admin.campaign.users")}</p><p className="font-black">{stats ? reportValue(stats.registrations) : t("admin.notAvailable")}</p></div><div className="rounded-xl bg-stone-50 p-2"><p className="text-xs text-stone-500">{t("admin.redemptions")}</p><p className="font-black">{stats ? reportValue(stats.redemptions) : t("admin.notAvailable")}</p></div><div className="rounded-xl bg-stone-50 p-2"><p className="text-xs text-stone-500">{t("admin.trials")}</p><p className="font-black">{stats ? reportValue(stats.trials) : t("admin.notAvailable")}</p></div><div className="rounded-xl bg-stone-50 p-2"><p className="text-xs text-stone-500">{t("admin.paidUsers")}</p><p className="font-black">{stats ? reportValue(stats.paid) : t("admin.notAvailable")}</p></div></div><p className="mt-2 text-xs text-stone-500">{t("admin.sales.conversionNote")}</p></Card>; })}</div>}</div>
      ) : null}

      {tab === "subscriptions" ? (
        <div className="flex flex-col gap-3"><Card><p className="text-sm text-stone-600">{t("admin.subscription.why")}</p><p className="mt-1 text-sm font-bold text-stone-500">{t("admin.subscription.readOnly")}</p><div className="mt-3 flex flex-wrap gap-2"><select value={subStatus} onChange={(event) => { setSubStatus(event.target.value); setSubPage(1); }} className={inputClass()} aria-label={t("admin.label.status")}><option value="">{t("admin.all")}</option>{["pending", "trialing", "active", "expired", "cancelled", "past_due"].map((value) => <option key={value} value={value}>{adminStatusLabel(value)}</option>)}</select></div></Card>{subscriptions === null ? <p className="py-4 text-center text-stone-500">{t("common.loading")}</p> : subscriptions.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <Card className="overflow-hidden p-0"><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-right text-sm"><thead className="bg-stone-50 text-xs text-stone-500"><tr><th className="p-3">{t("admin.label.user")}</th><th className="p-3">{t("admin.label.plan")}</th><th className="p-3">{t("admin.label.status")}</th><th className="p-3">{t("admin.sourceLabel")}</th><th className="p-3">{t("admin.label.coupon")}</th><th className="p-3">{t("admin.priceAmount")}</th><th className="p-3">{t("admin.label.start")}</th><th className="p-3">{t("admin.label.end")}</th><th className="p-3">{t("admin.trialDays")}</th><th className="p-3">{t("admin.createdAt")}</th></tr></thead><tbody>{subscriptions.map((subscription) => <tr key={subscription.id} className="border-t border-stone-100"><td className="p-3"><Link to={`/admin/users/${subscription.user_id}`} className="font-bold text-violet-700">{t("admin.label.user")} {faNum(subscription.user_id)}</Link></td><td className="p-3" dir="ltr">{subscription.plan_code}</td><td className="p-3"><Badge>{adminStatusLabel(subscription.status)}</Badge></td><td className="p-3">{adminSourceLabel(subscription.source)}</td><td className="p-3" dir="ltr">{subscription.coupon_code || t("admin.notAvailable")}</td><td className="p-3" dir="ltr">{subscription.price_amount_minor === null ? t("admin.notAvailable") : money(subscription.price_amount_minor, subscription.price_currency)}</td><td className="p-3" dir="ltr">{faDate(subscription.current_period_start)}</td><td className="p-3" dir="ltr">{faDate(subscription.current_period_end)}</td><td className="p-3" dir="ltr">{faDate(subscription.trial_ends_at)}</td><td className="p-3" dir="ltr">{faDateTime(subscription.created_at)}</td></tr>)}</tbody></table></div></Card>}<div className="flex items-center justify-between gap-2"><Button variant="secondary" disabled={subPage <= 1} onClick={() => setSubPage((value) => value - 1)}>{t("admin.pagination.previous")}</Button><span className="text-xs font-bold">{pageSummary(subPage, subscriptionTotal, SUB_PAGE_SIZE)}</span><Button variant="secondary" disabled={subPage >= Math.max(1, Math.ceil(subscriptionTotal / SUB_PAGE_SIZE))} onClick={() => setSubPage((value) => value + 1)}>{t("admin.pagination.next")}</Button></div></div>
      ) : null}

      {tab === "payments" ? (
        <div className="flex flex-col gap-3"><Card><p className="text-sm text-stone-600">{t("admin.payment.deferred")}</p><div className="mt-3 flex flex-wrap gap-2"><select value={payStatus} onChange={(event) => { setPayStatus(event.target.value); setPayPage(1); }} className={inputClass()} aria-label={t("admin.label.status")}><option value="">{t("admin.all")}</option>{["pending", "requires_action", "verified", "failed", "cancelled"].map((value) => <option key={value} value={value}>{adminStatusLabel(value)}</option>)}</select></div></Card>{payments === null ? <p className="py-4 text-center text-stone-500">{t("common.loading")}</p> : payments.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <Card className="overflow-hidden p-0"><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-right text-sm"><thead className="bg-stone-50 text-xs text-stone-500"><tr><th className="p-3">{t("admin.label.user")}</th><th className="p-3">{t("admin.label.plan")}</th><th className="p-3">{t("admin.label.status")}</th><th className="p-3">{t("admin.priceAmount")}</th><th className="p-3">{t("admin.discountValue")}</th><th className="p-3">{t("premium.payable")}</th><th className="p-3">{t("admin.label.coupon")}</th><th className="p-3">{t("admin.label.subscription")}</th><th className="p-3">{t("admin.providerLabel")}</th><th className="p-3">{t("admin.refLabel")}</th><th className="p-3">{t("admin.createdAt")}</th></tr></thead><tbody>{payments.map((payment) => <tr key={payment.id} className="border-t border-stone-100"><td className="p-3"><Link to={`/admin/users/${payment.user_id}`} className="font-bold text-violet-700">{t("admin.label.user")} {faNum(payment.user_id)}</Link><p className="mt-1 text-xs text-stone-500">#{faNum(payment.id)}</p></td><td className="p-3" dir="ltr">{payment.plan_code}</td><td className="p-3"><Badge>{adminStatusLabel(payment.status)}</Badge>{payment.failure_reason ? <p className="mt-1 max-w-[220px] text-xs text-red-600">{t("admin.payment.failed")}</p> : null}</td><td className="p-3" dir="ltr">{money(payment.price_amount_minor, payment.currency)}</td><td className="p-3" dir="ltr">{money(payment.discount_minor, payment.currency)}</td><td className="p-3" dir="ltr">{money(payment.final_amount_minor, payment.currency)}</td><td className="p-3" dir="ltr">{payment.coupon_code || t("admin.notAvailable")}</td><td className="p-3" dir="ltr">{payment.subscription_id ? `#${faNum(payment.subscription_id)}` : t("admin.notAvailable")}</td><td className="p-3" dir="ltr">{paymentProviderLabel(payment.provider)}</td><td className="p-3" dir="ltr">{payment.provider_ref || t("admin.notAvailable")}</td><td className="p-3" dir="ltr">{faDateTime(payment.created_at)}</td></tr>)}</tbody></table></div></Card>}<div className="flex items-center justify-between gap-2"><Button variant="secondary" disabled={payPage <= 1} onClick={() => setPayPage((value) => value - 1)}>{t("admin.pagination.previous")}</Button><span className="text-xs font-bold">{pageSummary(payPage, paymentTotal, SUB_PAGE_SIZE)}</span><Button variant="secondary" disabled={payPage >= Math.max(1, Math.ceil(paymentTotal / SUB_PAGE_SIZE))} onClick={() => setPayPage((value) => value + 1)}>{t("admin.pagination.next")}</Button></div></div>
      ) : null}
    </div>
  );
}
