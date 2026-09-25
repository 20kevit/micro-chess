import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { PageResult } from "../api/client";
import type { SupportStats, SupportTicket } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faDateTime, faNum } from "../lib/playerDisplay";

type TicketPage = PageResult<SupportTicket> | SupportTicket[];
const PAGE_SIZE = 20;
const STATUS_OPTIONS = ["open", "answered", "closed"] as const;

function unpack(value: TicketPage): { items: SupportTicket[]; total: number } {
  if (Array.isArray(value)) return { items: value, total: value.length };
  return value;
}

function statusLabel(status: string): string {
  if (status === "open") return t("admin.support.new");
  if (status === "answered") return t("admin.support.answered");
  if (status === "closed") return t("admin.support.closed");
  return t("admin.unknown");
}

function pageSummary(page: number, total: number): string {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return t("admin.pagination.summary")
    .replace("{page}", faNum(page))
    .replace("{pages}", faNum(pages))
    .replace("{total}", faNum(total));
}

export function AdminSupportPage() {
  const [rows, setRows] = useState<SupportTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<SupportStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    const params = { status: filter || undefined, category: category || undefined, page, page_size: PAGE_SIZE };
    const ticketRequest = typeof adminApi.supportTicketsPage === "function"
      ? adminApi.supportTicketsPage(params)
      : adminApi.supportTickets(params).then((items) => ({ items, total: items.length }));
    try {
      const [response, nextStats] = await Promise.all([
        ticketRequest,
        typeof adminApi.supportStats === "function"
          ? adminApi.supportStats().catch(() => null)
          : Promise.resolve(null),
      ]);
      const result = unpack(response as TicketPage);
      setRows(result.items);
      setTotal(result.total);
      setStats(nextStats);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [category, filter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const categories = useMemo(() => {
    const values = new Set((stats?.by_category ?? []).map((row) => row.category).filter(Boolean));
    if (category) values.add(category);
    return Array.from(values);
  }, [category, stats]);

  async function openTicket(id: number) {
    setNotice("");
    setDetailLoading(true);
    try {
      setSelected(await adminApi.supportTicket(id));
      setReply("");
    } catch {
      setNotice(t("common.error"));
    } finally {
      setDetailLoading(false);
    }
  }

  async function refreshSelected(id: number) {
    const detail = await adminApi.supportTicket(id);
    setSelected(detail);
  }

  async function respond() {
    if (!selected || !reply.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.respondSupport(selected.id, reply.trim());
      setReply("");
      await refreshSelected(selected.id);
      await load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function closeTicket() {
    if (!selected || busy) return;
    if (!window.confirm(t("admin.supportCloseConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.closeSupport(selected.id);
      await refreshSelected(selected.id);
      await load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function reopenTicket() {
    if (!selected || busy) return;
    if (!window.confirm(t("admin.support.reopenConfirm"))) return;
    if (typeof adminApi.reopenSupport !== "function") return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.reopenSupport(selected.id);
      await refreshSelected(selected.id);
      await load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.support")} subtitle={t("admin.support.practical")} />
      {stats ? <Card><div className="grid grid-cols-2 gap-2 md:grid-cols-4"><div><p className="text-xs text-stone-500">{t("admin.support.new")}</p><p className="text-xl font-black text-violet-700">{faNum(stats.open)}</p></div><div><p className="text-xs text-stone-500">{t("admin.support.answered")}</p><p className="text-xl font-black text-violet-700">{faNum(stats.answered)}</p></div><div><p className="text-xs text-stone-500">{t("admin.support.closed")}</p><p className="text-xl font-black text-violet-700">{faNum(stats.closed)}</p></div></div>{(stats.by_category ?? []).length > 0 ? <p className="mt-3 text-xs text-stone-500">{(stats.by_category ?? []).map((row) => `${row.category || t("admin.unknown")}: ${faNum(row.count)}`).join(" · ")}</p> : null}</Card> : null}
      <Card>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <label className="text-sm font-bold" htmlFor="admin-support-filter">{t("admin.supportFilter")}<select id="admin-support-filter" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1); setSelected(null); }} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"><option value="">{t("common.all")}</option>{STATUS_OPTIONS.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}</select></label>
          <label className="text-sm font-bold" htmlFor="admin-support-category">{t("admin.label.category")}<input id="admin-support-category" list="admin-support-categories" value={category} onChange={(event) => { setCategory(event.target.value); setPage(1); setSelected(null); }} placeholder={t("admin.categoryPlaceholder")} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" /></label>
        </div>
        <datalist id="admin-support-categories">{categories.map((value) => <option key={value} value={value} />)}</datalist>
      </Card>
      {notice ? <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}
      {loading ? <p className="py-8 text-center text-stone-500">{t("common.loading")}</p> : failed ? <div className="py-8 text-center"><p className="text-stone-500">{t("common.error")}</p><div className="mx-auto mt-3 max-w-xs"><Button onClick={() => void load()} className="w-full">{t("common.retry")}</Button></div></div> : rows.length === 0 ? <Card><p className="text-center text-stone-500">{t("admin.supportEmpty")}</p></Card> : <ul className="mt-3 flex flex-col gap-2">{rows.map((row) => <li key={row.id}><Card><div className="flex flex-wrap items-start justify-between gap-2"><button type="button" onClick={() => void openTicket(row.id)} className="min-h-[44px] text-right"><span className="font-black">#{faNum(row.id)} · {row.subject}</span><span className="mt-1 block text-xs text-stone-500">{row.category || t("admin.unknown")} · {t("admin.label.date")}: <span dir="ltr">{faDateTime(row.created_at)}</span></span></button><Badge>{statusLabel(row.status)}</Badge></div><div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-stone-500"><span>{t("admin.label.updated")}: <span dir="ltr">{faDateTime(row.updated_at)}</span></span>{row.user_id !== undefined ? <Link to={`/admin/users/${row.user_id}`} className="inline-flex min-h-[44px] items-center font-bold text-violet-700">{t("admin.support.userContext")}: {t("admin.label.user")} {faNum(row.user_id)}</Link> : null}</div></Card></li>)}</ul>}
      <div className="mt-3 flex items-center justify-between gap-2"><Button variant="secondary" disabled={loading || page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>{t("admin.pagination.previous")}</Button><span className="text-xs font-bold text-stone-500">{pageSummary(page, total)}</span><Button variant="secondary" disabled={loading || page >= Math.max(1, Math.ceil(total / PAGE_SIZE))} onClick={() => setPage((value) => value + 1)}>{t("admin.pagination.next")}</Button></div>
      {detailLoading ? <p className="mt-3 text-center text-stone-500">{t("common.loading")}</p> : selected ? <Card className="mt-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-black">{selected.subject}</h2><p className="mt-1 text-xs text-stone-500">#{faNum(selected.id)} · {selected.category || t("admin.unknown")}</p></div><Badge>{statusLabel(selected.status)}</Badge></div><div className="mt-2 flex flex-wrap gap-3 text-xs text-stone-500"><span>{t("admin.label.created")}: <span dir="ltr">{faDateTime(selected.created_at)}</span></span><span>{t("admin.label.updated")}: <span dir="ltr">{faDateTime(selected.updated_at)}</span></span>{selected.user_id !== undefined ? <Link to={`/admin/users/${selected.user_id}`} className="inline-flex min-h-[44px] items-center font-bold text-violet-700">{t("admin.support.userContext")}: {t("admin.label.user")} {faNum(selected.user_id)}</Link> : null}</div><p className="mt-2 text-xs text-stone-500">{t("admin.support.contextNote")}</p>{(selected.messages ?? []).length === 0 ? <p className="mt-4 text-sm text-stone-500">{t("admin.empty")}</p> : <ul className="mt-4 flex flex-col gap-2">{(selected.messages ?? []).map((message) => <li key={message.id} className={`rounded-xl px-3 py-2 ${message.author === "staff" ? "bg-violet-50" : "bg-stone-50"}`}><div className="flex items-center justify-between gap-2 text-xs font-bold text-stone-500"><span>{message.author === "staff" ? t("admin.support") : t("support.you")}</span><span dir="ltr">{faDateTime(message.created_at)}</span></div><p className="mt-1 whitespace-pre-wrap text-sm">{message.body}</p></li>)}</ul>}{selected.status !== "closed" ? <><label className="mt-4 block text-sm font-bold" htmlFor="admin-support-reply">{t("admin.supportRespond")}</label><textarea id="admin-support-reply" value={reply} onChange={(event) => setReply(event.target.value)} maxLength={2000} rows={3} className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2" /><div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2"><Button onClick={() => void respond()} disabled={busy || !reply.trim()}>{t("admin.supportRespond")}</Button><Button variant="secondary" onClick={() => void closeTicket()} disabled={busy}>{t("admin.supportClose")}</Button></div></> : <div className="mt-4"><Button variant="secondary" onClick={() => void reopenTicket()} disabled={busy}>{t("admin.support.reopen")}</Button></div>}</Card> : null}
    </div>
  );
}
