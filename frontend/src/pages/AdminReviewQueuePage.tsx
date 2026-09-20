import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { ReviewQueueItem } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

export function AdminReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  const load = () => {
    setLoading(true);
    setFailed(false);
    adminApi
      .reviewQueue({ status: status || undefined, page_size: 50 })
      .then((rows) => {
        setItems(rows);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  };

  useEffect(load, [status]);

  const act = (
    id: number,
    fn: (id: number, reason?: string) => Promise<unknown>,
    confirmKey: string,
  ) => {
    if (!window.confirm(t(confirmKey as never))) return;
    setBusyId(id);
    fn(id, reason || undefined)
      .then(() => load())
      .catch(() => undefined)
      .finally(() => setBusyId(null));
  };

  return (
    <AdminLayout>
      <PageHeader title={t("admin.reviewQueue")} subtitle={t("admin.reviewSubtitle")} />
      <Card>
        <div className="flex flex-col gap-2 md:flex-row">
          <select
            aria-label={t("admin.supportFilter")}
            className="min-h-[44px] rounded-xl border px-3"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">{t("admin.allStatuses")}</option>
            <option value="validated">{t("admin.statusValidated")}</option>
            <option value="reviewed">{t("admin.statusReviewed")}</option>
            <option value="approved">{t("admin.statusApproved")}</option>
            <option value="quarantined">{t("admin.statusArchived")}</option>
          </select>
          <input
            className="min-h-[44px] rounded-xl border px-3"
            placeholder={t("admin.reasonPlaceholder")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
      </Card>
      <div className="mt-3">
        {loading ? (
          <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
        ) : failed ? (
          <div className="py-8 text-center">
            <p className="text-stone-500">{t("common.error")}</p>
            <Button onClick={load} className="mx-auto mt-3 max-w-xs">
              {t("common.retry")}
            </Button>
          </div>
        ) : items.length === 0 ? (
          <Card>
            <p className="text-stone-500">{t("admin.empty")}</p>
          </Card>
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <li key={item.id}>
                <Card>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-black" dir="ltr">
                      #{faNum(item.id)} · {item.exercise_slug}
                    </span>
                    <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-700">
                      {item.severity} · {item.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-stone-500" dir="ltr">
                    attempts {faNum(item.attempts)} ·{" "}
                    {item.failure_rate === null ? "—" : `${Math.round(item.failure_rate * 100)}٪`} ·{" "}
                    {item.reasons.join(", ")}
                  </p>
                  <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Button
                      variant="secondary"
                      disabled={busyId === item.id}
                      onClick={() => act(item.id, adminApi.publishPuzzle, "admin.publish")}
                    >
                      {t("admin.publish")}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busyId === item.id}
                      onClick={() => act(item.id, adminApi.quarantinePuzzle, "admin.quarantineConfirm")}
                    >
                      {t("admin.quarantine")}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busyId === item.id}
                      onClick={() => act(item.id, adminApi.rejectPuzzle, "admin.rejectConfirm")}
                    >
                      {t("admin.reject")}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busyId === item.id}
                      onClick={() => act(item.id, adminApi.restorePuzzle, "admin.restoreConfirm")}
                    >
                      {t("admin.restore")}
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AdminLayout>
  );
}
