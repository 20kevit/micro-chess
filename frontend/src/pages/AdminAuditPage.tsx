import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AdminAuditRecord } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

export function AdminAuditPage() {
  const [rows, setRows] = useState<AdminAuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [action, setAction] = useState("");

  const load = () => {
    setLoading(true);
    setFailed(false);
    adminApi
      .audit({ action: action || undefined, page_size: 50 })
      .then((r) => {
        setRows(r);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  };

  useEffect(load, [action]);

  return (
    <AdminLayout>
      <PageHeader title={t("admin.auditLog")} subtitle={t("admin.subtitle")} />
      <Card>
        <input
          className="min-h-[44px] w-full rounded-xl border px-3"
          placeholder={t("admin.actionPlaceholder")}
          dir="ltr"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        />
      </Card>
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={load} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </div>
      ) : rows.length === 0 ? (
        <Card><p className="text-stone-500">{t("admin.noAudit")}</p></Card>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.id}>
              <Card>
                <p className="font-bold" dir="ltr">{row.action}</p>
                <p className="text-xs text-stone-500" dir="ltr">
                  {row.target_type}:{row.target_id} · actor {String(row.actor_user_id)} · {row.created_at}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </AdminLayout>
  );
}
