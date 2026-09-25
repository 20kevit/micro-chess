import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { ProductInsight } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { exerciseTitle, faNum } from "../lib/playerDisplay";

function severityLabel(value: string): string {
  if (value === "high") return t("admin.status.high");
  if (value === "medium") return t("admin.status.medium");
  if (value === "normal") return t("admin.status.normal");
  return t("admin.unknown");
}

function domainLabel(value: string): string {
  if (value === "content") return t("admin.contentHealth");
  if (value === "quality") return t("admin.puzzlePerformance");
  if (value === "sales") return t("admin.sales");
  if (value === "support") return t("admin.support");
  return t("admin.analytics");
}

function entityLabel(value: string, domain: string): string {
  if (value === "review_queue") return t("admin.reviewQueue");
  if (value === "puzzles") return t("admin.puzzles");
  if (value === "payments") return t("admin.payments");
  if (value === "support") return t("admin.support");
  if (domain === "content" && value) {
    const title = exerciseTitle(value);
    return title === value ? t("admin.unknown") : title;
  }
  return t("admin.unknown");
}

function titleFor(item: ProductInsight): string {
  if (item.key.startsWith("low_supply")) return t("admin.lowSupply");
  if (item.key === "review_queue_depth") return t("admin.reviewQueue");
  if (item.key === "high_failure_puzzles") return t("admin.failureRate");
  if (item.key === "payment_failures") return t("admin.payments");
  if (item.key === "open_support") return t("admin.support");
  return t("admin.insights");
}

function suggestionFor(item: ProductInsight): string {
  if (item.key.startsWith("low_supply")) return t("admin.reviewQueueOpen");
  if (item.key === "review_queue_depth") return t("admin.reviewQueueOpen");
  if (item.key === "high_failure_puzzles") return t("admin.puzzlePerformance");
  if (item.key === "payment_failures") return t("admin.payment.deferred");
  if (item.key === "open_support") return t("admin.support.practical");
  if (/[\u0600-\u06FF]/u.test(item.suggestion)) return item.suggestion;
  return t("admin.insights.suggestion");
}

function evidenceKeyLabel(key: string): string {
  if (key === "published") return t("admin.publishedCount");
  if (key === "threshold") return t("admin.insights.evidence");
  if (key === "pending") return t("admin.reviewQueue");
  if (key === "count") return t("admin.table.total");
  if (key === "sample_ids") return t("admin.label.object");
  if (key === "failed") return t("admin.status.failed");
  if (key === "open") return t("admin.supportFilter");
  return t("admin.insights.evidence");
}

function scalarLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") return t("admin.notAvailable");
  if (typeof value === "boolean") return value ? t("admin.yes") : t("admin.no");
  if (typeof value === "number") return faNum(value);
  return String(value);
}

function EvidenceValue({ value }: { value: unknown }): ReactNode {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span>{t("admin.notAvailable")}</span>;
    return <span>{value.map((entry) => scalarLabel(entry)).join("، ")}</span>;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span>{t("admin.notAvailable")}</span>;
    return (
      <ul className="mt-1 flex flex-col gap-1">
        {entries.map(([key, entry]) => (
          <li key={key} className="rounded-lg bg-stone-50 px-2 py-1">
            <span className="font-bold">{evidenceKeyLabel(key)}: </span>
            <EvidenceValue value={entry} />
          </li>
        ))}
      </ul>
    );
  }
  return <span dir={typeof value === "string" ? "ltr" : undefined}>{scalarLabel(value)}</span>;
}

function EvidenceList({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence);
  if (entries.length === 0) return <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>;
  return (
    <ul className="mt-2 flex flex-col gap-2">
      {entries.map(([key, value]) => (
        <li key={key} className="rounded-xl bg-stone-50 px-3 py-2 text-sm">
          <span className="font-bold">{evidenceKeyLabel(key)}: </span>
          <EvidenceValue value={value} />
        </li>
      ))}
    </ul>
  );
}

function linkFor(item: ProductInsight): string | null {
  if (item.domain === "content" && item.entity === "review_queue") return "/admin/review-queue";
  if (item.domain === "content" && item.entity && item.entity !== "puzzles") return `/admin/exercises/${item.entity}`;
  if (item.entity === "puzzles") return "/admin/puzzles";
  if (item.domain === "sales" || item.entity === "payments") return "/admin/sales?tab=payments";
  if (item.domain === "support" || item.entity === "support") return "/admin/support";
  return null;
}

export function AdminInsightsPage() {
  const [items, setItems] = useState<ProductInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    adminApi.insights()
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
    <div>
      <PageHeader title={t("admin.insights")} subtitle={t("admin.insightsSubtitle")} />
      <Card><p className="text-sm text-stone-600">{t("admin.insights.meaning")}</p></Card>
      {loading ? <p className="py-8 text-center text-stone-500">{t("common.loading")}</p> : failed ? <div className="py-8 text-center"><p className="text-stone-500">{t("common.error")}</p><div className="mx-auto mt-3 max-w-xs"><Button onClick={load} className="w-full">{t("common.retry")}</Button></div></div> : items.length === 0 ? <Card><p className="text-stone-500">{t("admin.empty")}</p></Card> : <ul className="mt-3 flex flex-col gap-3">{items.map((item) => { const link = linkFor(item); return <li key={item.key}><Card><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-black">{titleFor(item)}</h2><p className="mt-1 text-xs text-stone-500">{entityLabel(item.entity, item.domain)}</p></div><div className="flex flex-wrap gap-2"><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">{severityLabel(item.severity)}</span><span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-700">{domainLabel(item.domain)}</span></div></div><p className="mt-3 text-sm text-stone-700">{suggestionFor(item)}</p><h3 className="mt-3 text-sm font-black">{t("admin.insights.evidence")}</h3><EvidenceList evidence={item.evidence} />{link ? <Link to={link} className="mt-2 inline-flex min-h-[44px] items-center text-sm font-bold text-violet-700">{item.domain === "content" ? t("admin.workspace") : t("admin.details")}</Link> : null}</Card></li>; })}</ul>}
    </div>
  );
}
