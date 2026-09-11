import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiDetail, supportApi } from "../api/client";
import type { SupportTicket } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// One support conversation: messages plus an owner reply box (hidden
// once the ticket is closed). Server state stays authoritative.
export function SupportDetailPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    if (!Number.isFinite(ticketId)) {
      setFailed(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    supportApi
      .myTicket(ticketId)
      .then((res) => {
        setTicket(res);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  async function sendReply() {
    if (!reply.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await supportApi.reply(ticketId, reply.trim());
      setReply("");
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !ticket)
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={load} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );

  const closed = ticket.status === "closed";

  return (
    <div>
      <PageHeader title={ticket.subject} subtitle="" />
      <div className="mb-3">
        <Badge>
          {ticket.status === "answered"
            ? t("support.answered")
            : closed
              ? t("support.closed")
              : t("support.open")}
        </Badge>
      </div>
      <ul className="flex flex-col gap-2">
        {(ticket.messages ?? []).map((m) => (
          <li key={m.id}>
            <Card className={m.author === "staff" ? "border-violet-200 bg-violet-50" : undefined}>
              <p className="text-xs font-bold text-stone-500">
                {m.author === "staff" ? t("admin.support") : t("support.you")}
              </p>
              <p className="mt-1 whitespace-pre-wrap">{m.body}</p>
            </Card>
          </li>
        ))}
      </ul>
      {closed ? (
        <p className="mt-3 text-center text-sm text-stone-500">{t("support.closedNote")}</p>
      ) : (
        <Card>
          <label className="block text-sm font-bold" htmlFor="support-reply">
            {t("support.reply")}
          </label>
          <textarea
            id="support-reply"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder={t("support.replyPlaceholder")}
            maxLength={2000}
            rows={3}
            className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
          />
          <div className="mt-2">
            <Button onClick={sendReply} className="w-full" disabled={busy}>
              {t("support.reply")}
            </Button>
          </div>
          {notice ? <p className="mt-2 text-sm font-bold text-violet-700">{notice}</p> : null}
        </Card>
      )}
    </div>
  );
}
