import { useEffect, useState } from "react";
import { adminApi, adminBillingApi } from "../api/client";
import type { CampaignReport, SalesOverview } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

export function AdminSalesPage() {
  const [sales, setSales] = useState<SalesOverview | null>(null);
  const [report, setReport] = useState<CampaignReport[]>([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = () => {
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

  useEffect(load, []);

  if (loading) return <AdminLayout><p className="py-8 text-center text-stone-500">{t("common.loading")}</p></AdminLayout>;
  if (failed || !sales)
    return (
      <AdminLayout>
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={load} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </div>
      </AdminLayout>
    );

  return (
    <AdminLayout>
      <PageHeader title={t("admin.sales")} subtitle={t("admin.salesSubtitle")} />
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
      <Card>
        <h2 className="font-black">{t("admin.campaigns")}</h2>
        {report.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {report.map((row) => (
              <li key={row.slug} className="rounded-xl bg-stone-50 px-3 py-2">
                <p className="font-bold" dir="ltr">{row.slug}</p>
                <p className="text-xs text-stone-500" dir="ltr">
                  registrations {faNum(row.registrations)} · redemptions {faNum(row.redemptions)} · trials{" "}
                  {faNum(row.trials)} · paid {faNum(row.paid)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </AdminLayout>
  );
}
