import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { ProductInsight } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

export function AdminInsightsPage() {
  const [items, setItems] = useState<ProductInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    adminApi
      .insights()
      .then((rows) => {
        setItems(rows);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

  return (
    <AdminLayout>
      <PageHeader title={t("admin.insights")} subtitle={t("admin.insightsSubtitle")} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={load} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </div>
      ) : items.length === 0 ? (
        <Card><p className="text-stone-500">{t("admin.empty")}</p></Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.key}>
              <Card>
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-black">{item.title}</h2>
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700" dir="ltr">
                    {item.severity} · {item.domain}
                  </span>
                </div>
                <p className="mt-1 text-sm text-stone-600">{item.suggestion}</p>
                <p className="mt-1 text-xs text-stone-400" dir="ltr">{JSON.stringify(item.evidence)}</p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </AdminLayout>
  );
}
