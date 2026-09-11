import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiDetail, apiStatus, supportApi } from "../api/client";
import type { SupportTicket } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Own support requests: create a ticket, track its status, and continue
// the conversation. The server owns tickets, lifecycle, and identity;
// this page only renders what the server permits.
export function SupportPage() {
  const [rows, setRows] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    supportApi
      .myTickets()
      .then((res) => {
        setRows(res);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function send() {
    if (!subject.trim() || !message.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await supportApi.create({ subject: subject.trim(), message: message.trim() });
      setSubject("");
      setMessage("");
      setNotice(t("support.sent"));
      load();
    } catch (e) {
      setNotice(
        apiStatus(e) === 429 ? t("support.rateLimited") : apiDetail(e) || t("common.error"),
      );
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
    <div>
      <PageHeader title={t("support.title")} subtitle={t("support.subtitle")} />
      <Card>
        <h2 className="font-black">{t("support.newTitle")}</h2>
        <label className="mt-2 block text-sm font-bold" htmlFor="support-subject">
          {t("support.subject")}
        </label>
        <input
          id="support-subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder={t("support.subjectPlaceholder")}
          maxLength={200}
          className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3"
        />
        <label className="mt-2 block text-sm font-bold" htmlFor="support-message">
          {t("support.message")}
        </label>
        <textarea
          id="support-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={t("support.messagePlaceholder")}
          maxLength={2000}
          rows={3}
          className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
        />
        <div className="mt-2">
          <Button onClick={send} className="w-full" disabled={busy}>
            {t("support.send")}
          </Button>
        </div>
        {notice ? <p className="mt-2 text-sm font-bold text-violet-700">{notice}</p> : null}
      </Card>
      <div className="mt-3">
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
          <p className="py-8 text-center text-stone-500">{t("support.empty")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((row) => (
              <li key={row.id}>
                <Link to={`/support/${row.id}`} className="block">
                  <Card className="flex min-h-[44px] items-center justify-between gap-2">
                    <span className="font-bold">{row.subject}</span>
                    <Badge>{statusLabel(row.status)}</Badge>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
