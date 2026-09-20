import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminExerciseAnalyticsDetail, AdminExerciseDetail } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum, faPercent } from "../lib/playerDisplay";

export function AdminExerciseDetailPage() {
  const { slug } = useParams();
  const [exercise, setExercise] = useState<AdminExerciseDetail | null>(null);
  const [analytics, setAnalytics] = useState<AdminExerciseAnalyticsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    Promise.all([
      adminApi.exercise(slug),
      adminApi.exerciseAnalyticsDetail(slug, { period: "30d" }).catch(() => null),
    ])
      .then(([e, a]) => {
        setExercise(e);
        setAnalytics(a);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [slug]);

  return (
    <AdminLayout>
      <PageHeader title={t("admin.exerciseDetail")} subtitle={slug ?? ""} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed || !exercise ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={() => window.location.reload()} className="mx-auto mt-3 max-w-xs">
            {t("common.retry")}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Card>
            <h2 className="font-black">{exercise.title_fa}</h2>
            <p className="mt-1 text-sm text-stone-500" dir="ltr">{exercise.slug}</p>
            <p className="mt-1 text-sm text-stone-600">{exercise.description}</p>
          </Card>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Card className="text-center">
              <p className="text-2xl font-black text-violet-700">{faNum(exercise.puzzle_count)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.puzzleCount")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-violet-700">{faNum(exercise.published_count)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.publishedCount")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-amber-600">{faNum(exercise.needs_review_count)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.needsReview")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-sky-700">
                {exercise.success_rate === null ? "—" : faPercent(exercise.success_rate)}
              </p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.successRate")}</p>
            </Card>
          </div>
          {!analytics ? (
            <Card><p className="text-sm text-stone-500">{t("admin.empty")}</p></Card>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                <Card className="text-center">
                  <p className="text-2xl font-black text-violet-700">{faNum(analytics.attempts)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.attempts")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-2xl font-black text-violet-700">{faNum(analytics.unique_players)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.uniquePlayers")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-2xl font-black text-sky-700">{faPercent(analytics.accuracy)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("player.accuracy")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-2xl font-black text-emerald-700">{faNum(analytics.current_ratings)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.ratedPlayers")}</p>
                </Card>
              </div>
              {analytics.daily.length > 0 ? (
                <Card>
                  <h2 className="font-black">{t("admin.usageTrend")}</h2>
                  <div className="mt-2 flex h-24 items-end gap-1" dir="ltr" aria-hidden>
                    {analytics.daily.map((row) => {
                      const max = Math.max(1, ...analytics.daily.map((r) => r.attempts));
                      return (
                        <div
                          key={row.bucket_start}
                          title={`${row.bucket_start}: ${row.attempts}`}
                          className="min-w-2 flex-1 rounded-t bg-violet-300"
                          style={{ height: `${Math.max(4, Math.round((row.attempts / max) * 96))}px` }}
                        />
                      );
                    })}
                  </div>
                </Card>
              ) : null}
              <Card>
                <h2 className="font-black">{t("admin.supplyByStatus")}</h2>
                <ul className="mt-2 flex flex-col gap-1">
                  {analytics.supply_by_status.map((row) => (
                    <li key={row.status} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                      <span dir="ltr" className="font-bold">{row.status}</span>
                      <span>{faNum(row.count)}</span>
                    </li>
                  ))}
                  {analytics.supply_by_status.length === 0 && <p className="text-sm text-stone-500">{t("admin.empty")}</p>}
                </ul>
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.difficultyDist")}</h2>
                <ul className="mt-2 flex flex-col gap-1">
                  {analytics.difficulty_distribution.map((row) => (
                    <li key={String(row.difficulty)} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                      <span dir="ltr" className="font-bold">{String(row.difficulty ?? "—")}</span>
                      <span>{faNum(row.count)}</span>
                    </li>
                  ))}
                  {analytics.difficulty_distribution.length === 0 && <p className="text-sm text-stone-500">{t("admin.empty")}</p>}
                </ul>
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.mistakeDist")}</h2>
                <ul className="mt-2 flex flex-col gap-1">
                  {analytics.mistake_distribution.map((row) => (
                    <li key={row.mistake} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                      <span dir="ltr" className="font-bold">{row.mistake}</span>
                      <span>{faNum(row.count)}</span>
                    </li>
                  ))}
                  {analytics.mistake_distribution.length === 0 && <p className="text-sm text-stone-500">{t("admin.empty")}</p>}
                </ul>
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.recommendationOutcomes")}</h2>
                {analytics.recommendation_outcomes.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <p className="mt-1 text-xs text-stone-500" dir="ltr">
                    {analytics.recommendation_outcomes.map((r) => `${r.status}=${r.count}`).join(" · ")}
                  </p>
                )}
              </Card>
            </>
          )}
        </div>
      )}
    </AdminLayout>
  );
}
