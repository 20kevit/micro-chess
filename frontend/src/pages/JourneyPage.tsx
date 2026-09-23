import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { journeyApi, notifyApi, quotaApi } from "../api/client";
import type { Quest, Quota, TodayJourney } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { exerciseEntryTarget } from "../exercises/catalog";
import { t } from "../i18n";
import { exerciseTitle, faNum } from "../lib/playerDisplay";

// Daily Journey home: today's 3 quests, progress, obvious next action.
// Completing a quest leads naturally to the next; completing all three
// shows the daily completion state plus optional extra practice.
export function JourneyPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<TodayJourney | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const [finishing, setFinishing] = useState<number | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    Promise.all([journeyApi.today(tz), quotaApi.get().catch(() => null)])
      .then(([d, q]) => {
        setData(d);
        setQuota(q);
        setLoading(false);
        if (d.quests.length > 0) notifyApi.track("daily_journey_started").catch(() => {});
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function startAndGo(quest: Quest) {
    try {
      await journeyApi.startQuest(quest.id);
      notifyApi.track("quest_started", { quest_id: quest.id }).catch(() => {});
    } catch {
      // Best effort: navigation still works if start was already recorded.
    }
    navigate(`${exerciseEntryTarget(quest.exercise_slug)}?quest=${quest.id}`);
  }

  async function finishQuest(quest: Quest) {
    setFinishing(quest.id);
    setNotice("");
    try {
      const updated = await journeyApi.completeQuest(quest.id);
      setData((prev) =>
        prev
          ? {
              ...prev,
              quests: prev.quests.map((q) => (q.id === quest.id ? updated : q)),
              completed_count: prev.quests.every((q) =>
                q.id === quest.id ? updated.status === "completed" : q.status === "completed",
              )
                ? prev.total
                : prev.completed_count + (updated.status === "completed" ? 1 : 0),
            }
          : prev,
      );
      notifyApi.track("quest_completed", { quest_id: quest.id }).catch(() => {});
      if (updated.status === "completed") {
        // Refresh to recompute progress server-side.
        const fresh = await journeyApi.today();
        setData(fresh);
        quotaApi.get().then(setQuota).catch(() => {});
        if (fresh.is_complete) notifyApi.track("daily_journey_completed").catch(() => {});
      }
    } catch {
      setNotice(t("common.error"));
    } finally {
      setFinishing(null);
    }
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !data)
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

  const nextQuest = data.quests.find((q) => q.status !== "completed") ?? null;

  return (
    <div>
      <PageHeader
        title={`${t("journey.greeting")} 👋`}
        subtitle={t("journey.subtitle")}
      />
      <Card>
        <div className="flex items-center justify-between gap-2">
          <p className="font-black">{t("journey.progress")}</p>
          <p className="text-sm font-bold text-stone-500" aria-live="polite">
            {faNum(data.completed_count)} / {faNum(data.total)}
          </p>
        </div>
        <div
          className="mt-2 h-3 overflow-hidden rounded-full bg-stone-200"
          role="progressbar"
          aria-valuenow={data.completed_count}
          aria-valuemin={0}
          aria-valuemax={data.total}
          aria-label={t("journey.progress")}
        >
          <div
            className="h-full rounded-full bg-violet-600 transition-all"
            style={{ width: data.total ? `${(data.completed_count / data.total) * 100}%` : "0%" }}
          />
        </div>
        {nextQuest ? (
          <div className="mt-3">
            <Button onClick={() => startAndGo(nextQuest)} className="w-full">
              {data.completed_count === 0 ? t("journey.startToday") : t("journey.nextQuest")}
            </Button>
          </div>
        ) : null}
        {quota ? (
          <p className="mt-2 text-center text-xs text-stone-500" aria-live="polite">
            {t("quota.today")}: {faNum(quota.used)} {t("account.of")} {faNum(quota.limit)}
          </p>
        ) : null}
      </Card>

      {quota && !quota.can_practice ? (
        <Card className="mt-3 border-amber-300 bg-amber-50">
          <p className="font-black text-amber-800">{t("quota.reachedTitle")}</p>
          <p className="mt-1 text-sm text-amber-700">{t("quota.reachedHint")}</p>
          <Link to="/premium" className="mt-3 block">
            <Button className="w-full">{t("premium.cta")}</Button>
          </Link>
        </Card>
      ) : null}

      {data.is_complete ? (
        <Card className="mt-3 border-emerald-300 bg-emerald-50">
          <p className="font-black text-emerald-800">{t("journey.dayComplete")}</p>
          <p className="mt-1 text-sm text-emerald-700">{t("journey.dayCompleteHint")}</p>
          <Link to="/exercises" className="mt-3 block">
            <Button variant="secondary" className="w-full">
              {t("journey.extraPractice")}
            </Button>
          </Link>
        </Card>
      ) : null}

      <ul className="mt-3 flex flex-col gap-2">
        {data.quests.map((q) => (
          <li key={q.id}>
            <Card className={q.status === "completed" ? "border-emerald-200 bg-emerald-50/50" : undefined}>
              <div className="flex items-center justify-between gap-2">
                <p className="font-black">{q.title}</p>
                {q.status === "completed" ? <Badge>✓</Badge> : null}
              </div>
              <p className="mt-1 text-sm text-stone-500">{q.description}</p>
              <p className="mt-1 text-sm font-bold">{exerciseTitle(q.exercise_slug)}</p>
              <p className="mt-1 text-xs text-stone-500" aria-live="polite">
                {faNum(Math.min(q.progress, q.target_count))} / {faNum(q.target_count)}
              </p>
              <div className="mt-2 flex gap-2">
                <Button
                  onClick={() => startAndGo(q)}
                  disabled={q.status === "completed"}
                  className="flex-1"
                >
                  {t("play.start")}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => finishQuest(q)}
                  disabled={q.status === "completed" || finishing === q.id}
                  className="flex-1"
                >
                  {finishing === q.id ? t("common.loading") : t("journey.complete")}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>

      {data.quests.length === 0 ? (
        <Card>
          <p className="text-sm text-stone-500">{t("journey.empty")}</p>
          <Link to="/exercises" className="mt-3 block">
            <Button className="w-full">{t("player.goToExercises")}</Button>
          </Link>
        </Card>
      ) : null}

      {notice ? (
        <p role="alert" className="mt-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
          {notice}
        </p>
      ) : null}

      <Link to="/exercises" className="mt-3 block">
        <Button variant="secondary" className="w-full">
          {t("journey.extraPractice")}
        </Button>
      </Link>
    </div>
  );
}
