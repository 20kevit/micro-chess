import { useCallback, useEffect, useState } from "react";
import { apiDetail, relationshipsApi } from "../api/client";
import type { Relationship } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { useAuth } from "../lib/auth-context";

// Own relationship management: send invitations, accept incoming
// requests, revoke edges. Server authorization stays authoritative;
// this page only renders what the server permits.
export function RelationshipsPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [kind, setKind] = useState("coach");
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    relationshipsApi
      .list()
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

  async function sendInvite() {
    const target = username.trim().toLowerCase();
    if (!target || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await relationshipsApi.create({ kind, other_username: target });
      setUsername("");
      setNotice(t("rel.sent"));
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function accept(id: number) {
    setBusy(true);
    setNotice("");
    try {
      await relationshipsApi.accept(id);
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: number) {
    if (!window.confirm(t("rel.revokeConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await relationshipsApi.revoke(id);
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const myId = user?.id ?? -1;
  const incoming = rows.filter((r) => r.status === "pending" && r.created_by_user_id !== myId);
  const outgoing = rows.filter((r) => r.status === "pending" && r.created_by_user_id === myId);
  const active = rows.filter((r) => r.status === "active");
  const revoked = rows.filter((r) => r.status === "revoked");

  function kindLabel(row: Relationship): string {
    return row.kind === "coach" ? t("rel.kindCoach") : t("rel.kindParent");
  }

  function scopeHint(row: Relationship): string {
    return row.kind === "coach" ? t("rel.coachCanSee") : t("rel.parentCanSee");
  }

  return (
    <div>
      <PageHeader title={t("rel.title")} subtitle={t("rel.subtitle")} />
      <Card className="mb-4">
        <h2 className="mb-3 text-lg font-black text-stone-900">{t("rel.inviteTitle")}</h2>
        <label className="mb-1 block text-sm font-bold text-stone-600" htmlFor="rel-kind">
          {t("rel.kind")}
        </label>
        <select
          id="rel-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="mb-3 flex min-h-[44px] w-full items-center rounded-2xl border border-stone-200 bg-white px-3 text-base"
        >
          <option value="coach">{t("rel.kindCoach")}</option>
          <option value="parent">{t("rel.kindParent")}</option>
        </select>
        <label className="mb-1 block text-sm font-bold text-stone-600" htmlFor="rel-username">
          {t("rel.otherUsername")}
        </label>
        <input
          id="rel-username"
          dir="ltr"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mb-3 flex min-h-[44px] w-full items-center rounded-2xl border border-stone-200 bg-white px-3 text-base"
        />
        <Button onClick={sendInvite} disabled={busy || !username.trim()}>
          {t("rel.send")}
        </Button>
        {notice ? <p className="mt-2 text-sm font-bold text-stone-600">{notice}</p> : null}
      </Card>
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <Card>
          <p className="text-center font-bold text-stone-500">{t("common.error")}</p>
          <div className="mt-3 text-center">
            <Button variant="secondary" onClick={load}>
              {t("common.retry")}
            </Button>
          </div>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <p className="text-center font-bold text-stone-500">{t("rel.empty")}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {incoming.length > 0 ? (
            <section aria-label={t("rel.pendingIn")}>
              <h2 className="mb-2 text-lg font-black text-stone-900">{t("rel.pendingIn")}</h2>
              {incoming.map((row) => (
                <Card key={row.id} className="mb-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-black text-stone-900" dir="ltr">
                        {row.other_username}
                      </p>
                      <p className="text-sm text-stone-500">
                        {kindLabel(row)} · {t("rel.pending")}
                      </p>
                      <p className="mt-1 text-xs text-stone-500">{scopeHint(row)}</p>
                    </div>
                    <Button onClick={() => accept(row.id)} disabled={busy}>
                      {t("rel.accept")}
                    </Button>
                  </div>
                </Card>
              ))}
            </section>
          ) : null}
          {outgoing.length > 0 ? (
            <section aria-label={t("rel.pendingOut")}>
              <h2 className="mb-2 text-lg font-black text-stone-900">{t("rel.pendingOut")}</h2>
              {outgoing.map((row) => (
                <Card key={row.id} className="mb-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-black text-stone-900" dir="ltr">
                        {row.other_username}
                      </p>
                      <p className="text-sm text-stone-500">
                        {kindLabel(row)} · {t("rel.pending")}
                      </p>
                    </div>
                    <Button variant="ghost" onClick={() => revoke(row.id)} disabled={busy}>
                      {t("rel.revoke")}
                    </Button>
                  </div>
                </Card>
              ))}
            </section>
          ) : null}
          {active.length > 0 ? (
            <section aria-label={t("rel.active")}>
              <h2 className="mb-2 text-lg font-black text-stone-900">{t("rel.active")}</h2>
              {active.map((row) => (
                <Card key={row.id} className="mb-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-black text-stone-900" dir="ltr">
                        {row.other_username}
                      </p>
                      <p className="text-sm text-stone-500">
                        {kindLabel(row)} · {t("rel.active")}
                      </p>
                      <p className="mt-1 text-xs text-stone-500">{scopeHint(row)}</p>
                    </div>
                    <Button variant="secondary" onClick={() => revoke(row.id)} disabled={busy}>
                      {t("rel.revoke")}
                    </Button>
                  </div>
                </Card>
              ))}
            </section>
          ) : null}
          {revoked.length > 0 ? (
            <section aria-label={t("rel.revoked")}>
              <h2 className="mb-2 text-lg font-black text-stone-900">{t("rel.revoked")}</h2>
              {revoked.map((row) => (
                <Card key={row.id} className="mb-2">
                  <div className="flex items-center gap-2">
                    <p className="font-black text-stone-900" dir="ltr">
                      {row.other_username}
                    </p>
                    <Badge>{t("rel.revoked")}</Badge>
                  </div>
                </Card>
              ))}
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
