import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { exerciseTitle, faDate, faNum, faPercent, resultLabel } from "../lib/playerDisplay";

// Player home: profile greeting, own progress, and recent activity.
// Read model only — every number comes from the server dashboard endpoint.
export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    api
      .dashboard()
      .then((d) => {
        if (alive) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (alive) {
          setFailed(true);
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [retryKey]);

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !data)
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={() => setRetryKey((k) => k + 1)} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );

  const { profile, progress } = data;
  return (
    <div>
      <PageHeader
        title={`${t("player.greeting")} ${profile.display_name}`}
        subtitle={t("player.dashboardSubtitle")}
      />
      {progress.attempts === 0 ? (
        <Card>
          <p className="font-bold">{t("player.noActivity")}</p>
          <p className="mt-1 text-sm text-stone-500">{t("player.noActivityHint")}</p>
          <Link to="/exercises" className="mt-3 block">
            <Button className="w-full">{t("player.startFirst")}</Button>
          </Link>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-2">
            <Card className="text-center">
              <p className="text-2xl font-black text-violet-700">{faNum(progress.attempts)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("player.totalAttempts")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-emerald-700">{faNum(progress.correct)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("player.correctCount")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-sky-700">{faPercent(progress.accuracy)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("player.accuracy")}</p>
            </Card>
          </div>
          <Card>
            <h2 className="font-black">{t("player.perExercise")}</h2>
            <ul className="mt-2 flex flex-col gap-2">
              {progress.exercises.map((entry) => (
                <li
                  key={entry.exercise}
                  className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <span className="font-bold">{exerciseTitle(entry.exercise)}</span>
                  <span className="text-sm text-stone-500">
                    {faNum(entry.correct)} / {faNum(entry.attempts)} · {faPercent(entry.accuracy)}
                  </span>
                </li>
              ))}
            </ul>
            <Link to="/progress" className="mt-3 block">
              <Button variant="secondary" className="w-full">
                {t("player.viewProgress")}
              </Button>
            </Link>
          </Card>
          <Card>
            <h2 className="font-black">{t("player.recentActivity")}</h2>
            <ul className="mt-2 flex flex-col gap-2">
              {data.recent_attempts.map((attempt) => (
                <li
                  key={attempt.id}
                  className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <span className="font-bold">{exerciseTitle(attempt.exercise_slug)}</span>
                  <span className="flex items-center gap-2">
                    <span className="text-xs text-stone-500">{faDate(attempt.created_at)}</span>
                    <Badge>{resultLabel(attempt.result)}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <Link to="/exercises" className="block">
            <Button className="w-full">{t("player.goToExercises")}</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
