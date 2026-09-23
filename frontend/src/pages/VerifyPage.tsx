import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiDetail, notifyApi, verificationApi } from "../api/client";
import type { VerificationSession } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Phone verification via Telegram/Bale contact sharing. No phone
// typing, no SMS, no login change: the user picks a channel, gets a
// 6-digit pairing code, opens the bot, sends the code, then presses
// the official Share Contact button. This page polls the (masked)
// verification status until it flips or the session expires.
export function VerifyPage() {
  const navigate = useNavigate();
  const [channel, setChannel] = useState<"telegram" | "bale" | null>(null);
  const [session, setSession] = useState<VerificationSession | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const timer = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  async function start(next: "telegram" | "bale") {
    setBusy(true);
    setError("");
    setSession(null);
    setDone(false);
    stopPolling();
    try {
      const created = await verificationApi.createSession(next);
      setChannel(next);
      setSession(created);
      notifyApi.track("verification_started", { channel: next }).catch(() => {});
      const pollOnce = async () => {
        try {
          const status = await verificationApi.status();
          if (status.verified) {
            stopPolling();
            setDone(true);
            notifyApi.track("verification_completed", { channel: next }).catch(() => {});
            return true;
          }
        } catch {
          // Polling is best-effort; the user can also continue manually.
        }
        return false;
      };
      if (await pollOnce()) return;
      timer.current = window.setInterval(() => {
        void pollOnce().then((finished) => {
          if (finished) stopPolling();
        });
      }, 4000);
    } catch (e) {
      const detail = apiDetail(e);
      if (detail === "already_verified") {
        setDone(true);
      } else {
        setError(detail || t("common.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div>
        <PageHeader title={t("verify.successTitle")} subtitle={t("verify.successHint")} />
        <Card>
          <div className="flex flex-col gap-2">
            <Button onClick={() => navigate("/premium")}>{t("premium.cta")}</Button>
            <Link to="/" className="block">
              <Button variant="secondary" className="w-full">
                {t("journey.goQuests")}
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("verify.title")} subtitle={t("verify.subtitle")} />
      <Card>
        {session === null ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-stone-500">{t("verify.channelHint")}</p>
            <Button onClick={() => start("telegram")} disabled={busy}>
              {busy && channel === null ? t("common.loading") : t("verify.telegram")}
            </Button>
            <Button onClick={() => start("bale")} disabled={busy} variant="secondary">
              {busy ? t("common.loading") : t("verify.bale")}
            </Button>
            {error ? (
              <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {error}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-stone-500">{t("verify.codeHint")}</p>
            <p
              dir="ltr"
              aria-live="polite"
              className="rounded-2xl bg-violet-50 px-4 py-4 text-center text-3xl font-black tracking-[0.4em] text-violet-800"
            >
              {session.pairing_code}
            </p>
            {session.bot_url ? (
              <a href={session.bot_url} target="_blank" rel="noreferrer" className="block">
                <Button className="w-full">
                  {channel === "telegram" ? t("verify.openTelegram") : t("verify.openBale")}
                </Button>
              </a>
            ) : null}
            <p className="text-sm text-stone-500">{t("verify.waiting")}</p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => start(channel ?? "telegram")} disabled={busy} className="flex-1">
                {t("verify.newCode")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setSession(null);
                  setChannel(null);
                  stopPolling();
                }}
                className="flex-1"
              >
                {t("common.back")}
              </Button>
            </div>
            {error ? (
              <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {error}
              </p>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  );
}
