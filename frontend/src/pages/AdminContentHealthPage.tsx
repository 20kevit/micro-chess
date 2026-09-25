// Global content-health view: supply, review backlog, and attention
// reasons per exercise. Every alert links into the Exercise Workspace.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { ContentHealth } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum, faPercent } from "../lib/playerDisplay";

function supplyLabel(state: string): string {
  if (state === "attention") return t("admin.supplyAttention");
  if (state === "critical") return t("admin.supplyCritical");
  return t("admin.supplyHealthy");
}

function reasonLabel(reason: string): string {
  if (reason === "low_supply") return t("admin.reasonLowSupply");
  if (reason === "review_backlog") return t("admin.reasonReviewBacklog");
  if (reason === "quarantined_content") return t("admin.reasonQuarantined");
  if (reason === "no_generator") return t("admin.reasonNoGenerator");
  return t("admin.unknown");
}

export function AdminContentHealthPage() {
  const [health, setHealth] = useState<ContentHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attentionOnly, setAttentionOnly] = useState(false);

  async function load() {
    setLoading(true);
    setFailed(false);
    try {
      setHealth(await adminApi.contentHealth());
      setLoading(false);
    } catch {
      setFailed(true);
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const rows = (health?.exercises ?? []).filter(
    (row) => !attentionOnly || row.supply_state !== "healthy",
  );

  return (
    <>
      <PageHeader title={t("admin.contentHealth")} subtitle={t("admin.contentHealthSubtitle")} />
      <Card>
        <label className="flex min-h-[44px] items-center gap-2 text-sm font-bold">
          <input
            type="checkbox"
            checked={attentionOnly}
            onChange={(e) => setAttentionOnly(e.target.checked)}
          />
          {t("admin.attentionCount")}
          {health ? `: ${faNum(health.attention_count)}` : ""}
        </label>
      </Card>
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed || !health ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={() => void load()} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <p className="text-center text-stone-500">{t("admin.empty")}</p>
        </Card>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.slug}>
              <Card>
                <div className="flex min-h-[44px] items-center justify-between gap-2">
                  <Link
                    to={`/admin/exercises/${row.slug}`}
                    className="font-bold text-violet-700"
                  >
                    {row.title_fa}
                  </Link>
                  <Badge>{supplyLabel(row.supply_state)}</Badge>
                </div>
                <p className="mt-1 text-xs text-stone-500" dir="ltr">
                  {row.slug} · {row.is_active ? t("admin.statusActive") : t("admin.statusSuspended")}
                </p>
                <p className="mt-1 text-sm">
                  {t("admin.publishedCount")}: <b>{faNum(row.published)}</b> · {t("admin.needsReview")}:{" "}
                  <b>{faNum(row.needs_review)}</b> · {t("admin.successRate")}:{" "}
                  <b>{row.success_rate === null ? "—" : faPercent(row.success_rate)}</b>
                  {row.generator_available ? "" : ` · ${t("admin.reasonNoGenerator")}`}
                </p>
                {row.reasons.length > 0 ? (
                  <p className="mt-1 text-xs font-bold text-amber-700">
                    {row.reasons.map(reasonLabel).join(" · ")}
                  </p>
                ) : null}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
