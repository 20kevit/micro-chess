import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { SystemHealth } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

export function AdminSystemPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    adminApi
      .systemHealth()
      .then((h) => {
        setHealth(h);
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
      <PageHeader title={t("admin.system")} subtitle={t("admin.systemSubtitle")} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed || !health ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={load} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Card>
            <p className="font-black" dir="ltr">ok: {String(health.ok)}</p>
            <p className="text-sm text-stone-500" dir="ltr">
              database reachable: {String(health.database.reachable)} · schema ok:{" "}
              {String(health.schema_status.ok)} (expected {String(health.schema_status.expected)}, stored{" "}
              {String(health.schema_status.stored)})
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-violet-700">{faNum(health.puzzles.published)}/{faNum(health.puzzles.total)}</p>
            <p className="mt-1 text-xs text-stone-500">{t("admin.puzzlesPublished")}</p>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
}
