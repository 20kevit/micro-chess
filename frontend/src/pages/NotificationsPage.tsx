import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { notificationsApi, notifyApi, verificationApi } from "../api/client";
import type { ChannelLink, NotificationItem, NotificationPreference } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { pushState, subscribePush } from "../lib/push";

// Notification center: server-owned list with read/unread state plus
// preference controls. Refreshing preserves state (server is the source
// of truth, never localStorage).
function prefLabel(category: string): string {
  if (category === "account") return t("notif.account");
  if (category === "reminder") return t("notif.prefs.reminder");
  if (category === "journey") return t("notif.prefs.journey");
  if (category === "reward") return t("notif.prefs.reward");
  if (category === "system") return t("notif.prefs.system");
  return t("notif.support");
}

function channelLabel(channel: string): string {
  if (channel === "web_push") return t("notif.channel.web_push");
  if (channel === "telegram") return t("notif.channel.telegram");
  if (channel === "bale") return t("notif.channel.bale");
  if (channel === "sms") return t("notif.channel.sms");
  return t("notif.channel.in_app");
}

export function NotificationsPage() {
  const [rows, setRows] = useState<NotificationItem[]>([]);
  const [prefs, setPrefs] = useState<NotificationPreference[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    Promise.all([
      notificationsApi.list({ unread_only: unreadOnly }),
      notificationsApi.preferences(),
      verificationApi.status(),
    ])
      .then(([items, matrix, verification]) => {
         setRows(items);
         setPrefs(
          matrix.filter(
            (pref) => pref.channel !== "telegram" || verification.available_channels.includes("telegram"),
          ),
        );
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [unreadOnly]);

  useEffect(() => {
    load();
  }, [load]);

  async function markRead(id: number) {
    setNotice("");
    try {
      const updated = await notificationsApi.markRead(id);
      setRows((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch {
      setNotice(t("common.error"));
    }
  }

  async function togglePref(pref: NotificationPreference) {
    if (pref.mandatory) return;
    setNotice("");
    try {
      const updated = await notificationsApi.updatePreference({
        category: pref.category,
        channel: pref.channel,
        enabled: !pref.enabled,
      });
      setPrefs((prev) =>
        prev.map((p) =>
          p.category === updated.category && p.channel === updated.channel ? updated : p,
        ),
      );
    } catch {
      setNotice(t("common.error"));
    }
  }

  function typeTitle(ntype: string): string {
    if (ntype === "support.response") return t("notif.type.support.response");
    if (ntype === "support.closed") return t("notif.type.support.closed");
    if (ntype === "account.suspended") return t("notif.type.account.suspended");
    if (ntype === "account.reactivated") return t("notif.type.account.reactivated");
    return t("notif.type.system.info");
  }

  return (
    <div>
      <PageHeader title={t("notif.title")} subtitle={t("notif.subtitle")} />
      <JourneyNotifySection />
      <Card>
        <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm font-bold">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="h-5 w-5"
          />
          {t("notif.unreadOnly")}
        </label>
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
          <p className="py-8 text-center text-stone-500">{t("notif.empty")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((n) => (
              <li key={n.id}>
                <Card className={n.read_at ? undefined : "border-violet-300 bg-violet-50"}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-black">{typeTitle(n.type)}</p>
                    {n.read_at ? <Badge>{t("notif.read")}</Badge> : null}
                  </div>
                  {n.title && n.title !== n.type ? (
                    <p className="mt-1 font-bold">{n.title}</p>
                  ) : null}
                  {n.body ? <p className="mt-1 whitespace-pre-wrap text-sm">{n.body}</p> : null}
                  {!n.read_at ? (
                    <div className="mt-2">
                      <Button variant="secondary" onClick={() => markRead(n.id)}>
                        {t("notif.markRead")}
                      </Button>
                    </div>
                  ) : null}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Card>
        <h2 className="font-black">{t("notif.prefsTitle")}</h2>
        <p className="mt-1 text-sm text-stone-500">{t("notif.prefsSubtitle")}</p>
        <ul className="mt-2 flex flex-col gap-2">
          {prefs.map((p) => (
              <li
                key={`${p.category}:${p.channel}`}
                className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
              >
                <span className="text-sm font-bold">
                  {prefLabel(p.category)} · {channelLabel(p.channel)}{" "}
                  {p.mandatory ? (
                    <span className="text-xs font-normal text-stone-500">
                      ({t("notif.mandatory")})
                    </span>
                  ) : null}
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={p.enabled}
                  aria-label={`${prefLabel(p.category)} ${channelLabel(p.channel)}`}
                  disabled={p.mandatory}
                  onClick={() => togglePref(p)}
                  className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl px-3 text-sm font-bold ${
                    p.enabled ? "bg-violet-600 text-white" : "bg-stone-200 text-stone-600"
                  } ${p.mandatory ? "opacity-60" : ""}`}
                >
                  {p.enabled ? "✓" : "–"}
                </button>
              </li>
            ))}
        </ul>
        {notice ? <p className="mt-2 text-sm font-bold text-violet-700">{notice}</p> : null}
      </Card>
    </div>
  );
}

// P11 journey notification controls: Web Push subscribe (asked only here,
// after the user sees the value), Telegram/Bale linking, and the
// extended preference matrix. Channels stay independent.
function JourneyNotifySection() {
  const [prefs, setPrefs] = useState<NotificationPreference[]>([]);
  const [links, setLinks] = useState<ChannelLink[]>([]);
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const [push, setPush] = useState<string>("prompt");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const vapidKey = import.meta.env.VITE_VAPID_PUBLIC_KEY ?? "";

  useEffect(() => {
    notifyApi.preferences().then(setPrefs).catch(() => {});
    notifyApi.channelLinks().then(setLinks).catch(() => {});
    verificationApi
      .status()
      .then((status) => setAvailableChannels(status.available_channels))
      .catch(() => setMessage(t("common.error")));
    pushState().then(setPush).catch(() => {});
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  async function toggle(pref: NotificationPreference) {
    if (pref.mandatory) return;
    try {
      const updated = await notifyApi.updatePreference({
        category: pref.category,
        channel: pref.channel,
        enabled: !pref.enabled,
      });
      setPrefs((prev) =>
        prev.map((p) =>
          p.category === updated.category && p.channel === updated.channel ? updated : p,
        ),
      );
    } catch {
      setMessage(t("common.error"));
    }
  }

  async function enablePush() {
    setBusy(true);
    setMessage("");
    await notifyApi.track("notification_permission_prompted").catch(() => {});
    const ok = await subscribePush(vapidKey);
    setPush(await pushState().catch(() => "unsupported" as const));
    if (!ok) setMessage(t("notif.push.denied"));
    setBusy(false);
  }

  async function unlink(channel: string) {
    try {
      await notifyApi.unlink(channel);
      setLinks((prev) => prev.filter((l) => l.channel !== channel));
    } catch {
      setMessage(t("common.error"));
    }
  }

  const linked = (channel: string) => links.some((l) => l.channel === channel && l.linked);

  return (
    <Card className="mb-3">
      <h2 className="font-black">{t("notif.journeyTitle")}</h2>
      <p className="mt-1 text-sm text-stone-500">{t("notif.push.explain")}</p>
      <div className="mt-2 flex flex-col gap-2">
        {push === "unsupported" ? null : push === "subscribed" ? (
          <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-700">
            {t("notif.push.enabled")}
          </p>
        ) : (
          <Button onClick={enablePush} disabled={busy || push === "denied" || !vapidKey}>
            {busy ? t("common.loading") : t("notif.push.enable")}
          </Button>
        )}
        {push === "denied" ? (
          <p className="text-sm text-stone-500">{t("notif.push.denied")}</p>
        ) : null}
        {(["telegram", "bale"] as const)
          .filter((channel) => availableChannels.includes(channel))
          .map((channel) => (
          <div
            key={channel}
            className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
          >
            <span className="text-sm font-bold">
              {channel === "telegram" ? t("notif.channel.telegram") : t("notif.channel.bale")}
            </span>
            {linked(channel) ? (
              <Button variant="secondary" onClick={() => unlink(channel)}>
                {t("notif.link.unlink")}
              </Button>
            ) : (
              <Link
                to="/verify"
                className="flex min-h-[44px] items-center justify-center rounded-xl border border-stone-200 bg-white px-4 text-sm font-bold text-stone-700"
              >
                {channel === "telegram" ? t("notif.link.telegram") : t("notif.link.bale")}
              </Link>
            )}
          </div>
        ))}
      </div>
      {prefs.length ? (
        <ul className="mt-2 flex flex-col gap-2">
          {prefs
            .filter(
              (p) =>
                p.channel !== "in_app" &&
                (p.channel !== "telegram" || availableChannels.includes("telegram")),
            )
            .map((p) => (
              <li
                key={`${p.category}:${p.channel}`}
                className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
              >
                <span className="text-sm font-bold">
                  {prefLabel(p.category)} · {channelLabel(p.channel)}
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={p.enabled}
                  aria-label={`${p.category} ${p.channel}`}
                  onClick={() => toggle(p)}
                  className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl px-3 text-sm font-bold ${
                    p.enabled ? "bg-violet-600 text-white" : "bg-stone-200 text-stone-600"
                  }`}
                >
                  {p.enabled ? "✓" : "–"}
                </button>
              </li>
            ))}
        </ul>
      ) : null}
      {message ? <p className="mt-2 text-sm font-bold text-violet-700">{message}</p> : null}
    </Card>
  );
}
