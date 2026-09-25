import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { PageResult } from "../api/client";
import type { AdminAuditRecord } from "../api/types";
import type { FaKey } from "../i18n/fa";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faDateTime, faNum } from "../lib/playerDisplay";

type AuditPage = PageResult<AdminAuditRecord> | AdminAuditRecord[];
type AuditRequestParams = {
  action?: string;
  target_type?: string;
  actor_id?: number;
  page?: number;
  page_size?: number;
  target_id?: number;
  date_from?: string;
  date_to?: string;
};
const PAGE_SIZE = 20;

const ACTION_KEYS: Record<string, FaKey> = {
  "users.suspend": "admin.suspend",
  "users.reactivate": "admin.reactivate",
  "roles.assign": "admin.assignRole",
  "roles.revoke": "admin.revokeRole",
  "support.create": "admin.support.new",
  "support.reply": "admin.supportRespond",
  "support.respond": "admin.supportRespond",
  "support.close": "admin.supportClose",
  "support.reopen": "admin.support.reopen",
  "puzzles.create": "admin.createDraft",
  "puzzles.update": "admin.saveChanges",
  "puzzles.delete": "admin.deleteBlocked",
  "puzzles.publish": "admin.publish",
  "puzzles.validate": "admin.validate",
  "puzzles.review": "admin.reviewDecision",
  "puzzles.approve": "admin.approve",
  "puzzles.quarantine": "admin.quarantine",
  "puzzles.release": "admin.release",
  "puzzles.reject": "admin.reject",
  "puzzles.restore": "admin.restore",
  "puzzles.retire": "admin.retire",
  "billing.coupon_created": "admin.createCoupon",
  "billing.coupon_rejected": "admin.status.rejected",
  "billing.plan_created": "admin.createPlan",
  "billing.price_created": "admin.createPrice",
  "billing.campaign_created": "admin.createCampaign",
  "billing.coupon_updated": "admin.saveChanges",
  "billing.plan_updated": "admin.saveChanges",
  "billing.price_updated": "admin.saveChanges",
  "billing.campaign_updated": "admin.saveChanges",
  "generators.cancel": "admin.cancel",
  "generators.run": "admin.runGenerator",
  "exercises.create": "admin.exerciseCreate",
  "exercises.update": "admin.saveChanges",
};
const TARGET_KEYS: Record<string, FaKey> = {
  user: "admin.label.user",
  users: "admin.label.user",
  puzzle: "admin.puzzles",
  support_ticket: "admin.support",
  plan: "admin.label.plan",
  price: "admin.plans",
  coupon: "admin.coupons",
  campaign: "admin.label.campaign",
  plan_price: "admin.plans",
  relationship: "admin.relationships",
  assignment: "admin.assignments",
  assessment: "admin.assessments",
  subscription: "admin.subscriptions",
  payment: "admin.payments",
  exercise: "admin.exercises",
  generator_run: "admin.generatorRuns",
};
const METADATA_KEYS: Record<string, FaKey> = {
  subject: "support.subject",
  username: "auth.username",
  user_id: "admin.label.user",
  target_id: "admin.label.object",
  from_status: "admin.label.status",
  to_status: "admin.label.status",
  reason: "admin.label.reason",
  role: "auth.roles",
  code: "admin.planCode",
  slug: "admin.campaignSlug",
  generator: "admin.generators",
  browser: "admin.label.browser",
  device: "admin.label.device",
  request_id: "admin.label.requestId",
  status: "admin.label.status",
  plan_code: "admin.label.plan",
};

function unpack(value: AuditPage): { items: AdminAuditRecord[]; total: number } {
  if (Array.isArray(value)) return { items: value, total: value.length };
  return value;
}

function actionLabel(action: string): string {
  const mapped = ACTION_KEYS[action];
  if (mapped) return t(mapped);
  if (action.startsWith("puzzles.")) return t("admin.puzzles");
  if (action.startsWith("billing.")) return t("admin.sales");
  if (action.startsWith("support.")) return t("admin.support");
  if (action.startsWith("users.")) return t("admin.users");
  if (action.startsWith("roles.")) return t("auth.roles");
  if (action.startsWith("relationship")) return t("admin.relationships");
  if (action.startsWith("assignment")) return t("admin.assignments");
  if (action.startsWith("assessment")) return t("admin.assessments");
  return t("admin.unknown");
}

function targetLabel(target: string): string {
  const mapped = TARGET_KEYS[target];
  if (mapped) return t(mapped);
  if (target.includes("support")) return t("admin.support");
  if (target.includes("payment")) return t("admin.payments");
  if (target.includes("coupon")) return t("admin.coupons");
  if (target.includes("campaign")) return t("admin.label.campaign");
  return t("admin.unknown");
}

function resultLabel(result: string): string {
  if (result === "ok" || result === "success" || result === "pass") return t("admin.status.verified");
  if (result === "fail" || result === "error" || result === "denied") return t("admin.status.failed");
  if (result === "partial") return t("admin.status.pending");
  return t("admin.unknown");
}

function metadataKeyLabel(key: string): string {
  return t(METADATA_KEYS[key] ?? "admin.audit.metadata");
}

function metadataValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return t("admin.notAvailable");
  if (typeof value === "boolean") return value ? t("admin.yes") : t("admin.no");
  if (typeof value === "number") return faNum(value);
  if (Array.isArray(value)) return value.map((entry) => metadataValue(entry)).join("، ");
  if (typeof value === "object") return t("admin.details");
  return t("admin.details");
}

function pageSummary(page: number, total: number): string {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return t("admin.pagination.summary")
    .replace("{page}", faNum(page))
    .replace("{pages}", faNum(pages))
    .replace("{total}", faNum(total));
}

export function AdminAuditPage() {
  const [rows, setRows] = useState<AdminAuditRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [action, setAction] = useState("");
  const [actorId, setActorId] = useState("");
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    const numericTargetId = Number(targetId);
    const params: AuditRequestParams = {
      action: action || undefined,
      target_type: targetType || undefined,
      target_id: targetId && Number.isInteger(numericTargetId) ? numericTargetId : undefined,
      actor_id: actorId && Number.isInteger(Number(actorId)) ? Number(actorId) : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
      page_size: PAGE_SIZE,
    };
    try {
      const response = typeof adminApi.auditPage === "function"
        ? await adminApi.auditPage(params)
        : await adminApi.audit(params);
      const result = unpack(response as AuditPage);
      setRows(result.items);
      setTotal(result.total);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [action, actorId, dateFrom, dateTo, page, targetId, targetType]);

  useEffect(() => {
    void load();
  }, [load]);

  function resetPage() {
    setPage(1);
  }

  return (
    <div>
      <PageHeader title={t("admin.auditLog")} subtitle={t("admin.audit.purpose")} />
      <Card>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <label className="text-sm font-bold" htmlFor="admin-audit-action">{t("admin.label.actions")}<input id="admin-audit-action" value={action} onChange={(event) => { setAction(event.target.value); resetPage(); }} placeholder={t("admin.actionPlaceholder")} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" dir="ltr" /></label>
          <label className="text-sm font-bold" htmlFor="admin-audit-actor">{t("admin.audit.actorFilter")}<input id="admin-audit-actor" value={actorId} onChange={(event) => { setActorId(event.target.value); resetPage(); }} type="number" min="1" className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" dir="ltr" /></label>
          <label className="text-sm font-bold" htmlFor="admin-audit-target-type">{t("admin.audit.objectType")}<input id="admin-audit-target-type" value={targetType} onChange={(event) => { setTargetType(event.target.value); resetPage(); }} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" dir="ltr" /></label>
          <label className="text-sm font-bold" htmlFor="admin-audit-target-id">{t("admin.audit.objectId")}<input id="admin-audit-target-id" value={targetId} onChange={(event) => { setTargetId(event.target.value); resetPage(); }} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" dir="ltr" /></label>
          <label className="text-sm font-bold" htmlFor="admin-audit-from">{t("admin.audit.dateFrom")}<input id="admin-audit-from" type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); resetPage(); }} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" /></label>
          <label className="text-sm font-bold" htmlFor="admin-audit-to">{t("admin.audit.dateTo")}<input id="admin-audit-to" type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); resetPage(); }} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" /></label>
        </div>
      </Card>
      {loading ? <p className="py-8 text-center text-stone-500">{t("common.loading")}</p> : failed ? <div className="py-8 text-center"><p className="text-stone-500">{t("common.error")}</p><div className="mx-auto mt-3 max-w-xs"><Button onClick={() => void load()} className="w-full">{t("common.retry")}</Button></div></div> : rows.length === 0 ? <Card><p className="text-center text-stone-500">{t("admin.noAudit")}</p></Card> : <ul className="mt-3 flex flex-col gap-2">{rows.map((row) => <li key={row.id}><Card><div className="grid grid-cols-1 gap-2 md:grid-cols-2"><div><p className="text-xs text-stone-500">{t("admin.label.actor")}</p><p className="mt-1 font-bold">{row.actor_user_id === null ? t("admin.unknown") : <Link to={`/admin/users/${row.actor_user_id}`} className="text-violet-700">{t("admin.label.actor")} {faNum(row.actor_user_id)}</Link>}</p></div><div><p className="text-xs text-stone-500">{t("admin.label.actions")}</p><p className="mt-1 font-bold">{actionLabel(row.action)}</p></div><div><p className="text-xs text-stone-500">{t("admin.label.object")}</p><p className="mt-1 font-bold">{targetLabel(row.target_type)} <span dir="ltr">#{row.target_id}</span></p></div><div><p className="text-xs text-stone-500">{t("admin.label.date")}</p><p className="mt-1 font-bold" dir="ltr">{faDateTime(row.created_at)}</p></div></div><div className="mt-3 flex items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"><span className="text-xs text-stone-500">{t("admin.label.result")}</span><span className="text-sm font-black">{resultLabel(row.result)}</span></div><details className="mt-2"><summary className="min-h-[44px] cursor-pointer py-3 text-sm font-bold text-violet-700">{t("admin.audit.metadata")}</summary>{Object.keys(row.metadata ?? {}).length === 0 ? <p className="text-sm text-stone-500">{t("admin.empty")}</p> : <dl className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">{Object.entries(row.metadata ?? {}).map(([key, value]) => <div key={key} className="rounded-xl bg-stone-50 px-3 py-2"><dt className="text-xs font-bold text-stone-500">{metadataKeyLabel(key)}</dt><dd className="mt-1 text-sm">{metadataValue(value)}</dd></div>)}</dl>}</details></Card></li>)}</ul>}
      <div className="mt-3 flex items-center justify-between gap-2"><Button variant="secondary" disabled={loading || page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>{t("admin.pagination.previous")}</Button><span className="text-xs font-bold text-stone-500">{pageSummary(page, total)}</span><Button variant="secondary" disabled={loading || page >= Math.max(1, Math.ceil(total / PAGE_SIZE))} onClick={() => setPage((value) => value + 1)}>{t("admin.pagination.next")}</Button></div>
    </div>
  );
}
