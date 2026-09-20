import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminExerciseDetail } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

export function AdminExerciseDetailPage() {
  const { slug } = useParams();
  const [exercise, setExercise] = useState<AdminExerciseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!slug) return;
    adminApi
      .exercise(slug)
      .then((e) => {
        setExercise(e);
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
          <div className="grid grid-cols-2 gap-2">
            <Card className="text-center">
              <p className="text-2xl font-black text-violet-700">{faNum(exercise.puzzle_count)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.puzzleCount")}</p>
            </Card>
            <Card className="text-center">
              <p className="text-2xl font-black text-violet-700">{faNum(exercise.attempts_count)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("admin.attempts")}</p>
            </Card>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
