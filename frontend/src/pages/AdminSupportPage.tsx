import { useCallback, useEffect, useState } from "react";
import { apiDetail, adminApi } from "../api/client";
import type { SupportStats, SupportTicket } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

// Staff support queue: list tickets, read the conversation, respond,
// and close. Every action authorizes server-side; this page only
// renders what the server permits.
export function AdminSupportPage() {
  const [rows, setRows] = useState<SupportTicket[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState("");
  const [stats, setStats] = useState<SupportStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    Promise.all([
      adminApi.supportTickets({
        status: filter || undefined,
        category: category || undefined,
      }),
      adminApi.supportStats().catch(() => null),
    ])
      .then(([res, st]) => {
        setRows(res);
        setStats(st);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [filter, category]);

  useEffect(() => {
    load();
  }, [load]);

  async function open(id: number) {
    setNotice("");
    try {
      const detail = await adminApi.supportTicket(id);
      setSelected(detail);
      setReply("");
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    }
  }

  async function respond() {
    if (!selected || !reply.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.respondSupport(selected.id, reply.trim());
      setReply("");
      const detail = await adminApi.supportTicket(selected.id);
      setSelected(detail);
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function close() {
    if (!selected || busy) return;
    if (!window.confirm(t("admin.supportCloseConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      const updated = await adminApi.closeSupport(selected.id);
      const detail = await adminApi.supportTicket(updated.id);
      setSelected(detail);
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function statusLabel(status: string): string {
    if (status === "answered") return t("support.answered");
    if (status === "closed") return t("support.closed");
    return t("support.open");
  }

  return (
    <AdminLayout>
      <PageHeader title={t("admin.support")} subtitle={t("admin.supportSubtitle")} />
      {stats ? (
        <Card>
          <p className="text-sm text-stone-500">
            {t("support.open")}: {faNum(stats.open)} · {t("support.answered")}: {faNum(stats.answered)} ·{" "}
            {t("support.closed")}: {faNum(stats.closed)}
          </p>
          {stats.by_category.length > 0 ? (
            <p className="mt-1 text-xs text-stone-400" dir="ltr">
              {stats.by_category.map((c) => `${c.category || "—"}=${c.count}`).join(" · ")}
            </p>
          ) : null}
        </Card>
      ) : null}
      <Card>
        <label className="block text-sm font-bold" htmlFor="admin-support-filter">
          {t("admin.supportFilter")}
        </label>
        <select
          id="admin-support-filter"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setSelected(null);
          }}
          className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3"
        >
          <option value="">{t("common.all")}</option>
          <option value="open">{t("support.open")}</option>
          <option value="answered">{t("support.answered")}</option>
          <option value="closed">{t("support.closed")}</option>
        </select>
        <input
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setSelected(null);
          }}
          placeholder={t("admin.categoryPlaceholder")}
          dir="ltr"
          className="mt-2 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3"
        />
      </Card>
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={load} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      ) : rows.length === 0 ? (
        <p className="py-8 text-center text-stone-500">{t("admin.supportEmpty")}</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => open(row.id)}
                className="block w-full text-start"
              >
                <Card className="flex min-h-[44px] items-center justify-between gap-2">
                  <span>
                    <span className="font-bold">#{faNum(row.id)}</span>{" "}
                    <span className="font-bold">{row.subject}</span>
                  </span>
                  <Badge>{statusLabel(row.status)}</Badge>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected ? (
        <Card>
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-black">{selected.subject}</h2>
            <Badge>{statusLabel(selected.status)}</Badge>
          </div>
          <ul className="mt-2 flex flex-col gap-2">
            {(selected.messages ?? []).map((m) => (
              <li
                key={m.id}
                className={`rounded-xl px-3 py-2 ${
                  m.author === "staff" ? "bg-violet-50" : "bg-stone-50"
                }`}
              >
                <p className="text-xs font-bold text-stone-500">
                  {m.author === "staff" ? t("admin.support") : t("support.you")}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{m.body}</p>
              </li>
            ))}
          </ul>
          {selected.status !== "closed" ? (
            <>
              <label className="mt-2 block text-sm font-bold" htmlFor="admin-support-reply">
                {t("admin.supportRespond")}
              </label>
              <textarea
                id="admin-support-reply"
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                maxLength={2000}
                rows={3}
                className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
              />
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button onClick={respond} disabled={busy}>
                  {t("admin.supportRespond")}
                </Button>
                <Button variant="secondary" onClick={close} disabled={busy}>
                  {t("admin.supportClose")}
                </Button>
              </div>
            </>
          ) : null}
          {notice ? <p className="mt-2 text-sm font-bold text-violet-700">{notice}</p> : null}
        </Card>
      ) : null}
    </AdminLayout>
  );
}
