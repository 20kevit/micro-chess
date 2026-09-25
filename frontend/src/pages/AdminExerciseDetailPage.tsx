// Exercise Workspace: overview, content, puzzles, generate, review,
// quality, difficulty, learning, analytics, settings — operated from
// one coherent admin experience. All numbers come from real backend
// aggregates; unavailable capabilities render truthful empty states.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type {
  AdminExerciseAnalyticsDetail,
  AdminExerciseDetail,
  ExerciseLearning,
  ExerciseQuality,
  Generator,
} from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum, faPercent } from "../lib/playerDisplay";

type Tab =
  | "overview"
  | "puzzles"
  | "generate"
  | "review"
  | "quality"
  | "difficulty"
  | "learning"
  | "analytics"
  | "settings";

const TABS: Tab[] = [
  "overview",
  "puzzles",
  "generate",
  "review",
  "quality",
  "difficulty",
  "learning",
  "analytics",
  "settings",
];

function tabLabel(tab: Tab): string {
  if (tab === "overview") return t("admin.tabOverview");
  if (tab === "puzzles") return t("admin.tabPuzzles");
  if (tab === "generate") return t("admin.tabGenerate");
  if (tab === "review") return t("admin.tabReview");
  if (tab === "quality") return t("admin.tabQuality");
  if (tab === "difficulty") return t("admin.tabDifficulty");
  if (tab === "learning") return t("admin.tabLearning");
  if (tab === "analytics") return t("admin.tabAnalytics");
  return t("admin.tabSettings");
}

function statusLabel(status: string): string {
  if (status === "draft") return t("admin.statusDraft");
  if (status === "validated") return t("admin.statusValidated");
  if (status === "reviewed") return t("admin.statusReviewed");
  if (status === "approved") return t("admin.statusApproved");
  if (status === "published") return t("admin.statusPublished");
  if (status === "quarantined") return t("admin.status.quarantined");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "retired" || status === "archived") return t("admin.status.retired");
  return t("admin.unknown");
}

function reasonLabel(reason: string): string {
  if (reason === "low_supply") return t("admin.reasonLowSupply");
  if (reason === "review_backlog") return t("admin.reasonReviewBacklog");
  if (reason === "quarantined_content") return t("admin.reasonQuarantined");
  if (reason === "validation_failures") return t("admin.reasonValidationFailures");
  if (reason === "high_failure_puzzles") return t("admin.reasonHighFailure");
  if (reason === "thin_difficulty_coverage") return t("admin.reasonThinCoverage");
  if (reason === "no_generator") return t("admin.reasonNoGenerator");
  return t("admin.unknown");
}

function supplyStateLabel(state: string): string {
  if (state === "healthy") return t("admin.supplyHealthy");
  if (state === "attention") return t("admin.supplyAttention");
  if (state === "critical") return t("admin.supplyCritical");
  return t("admin.unknown");
}

function metricLabel(value: string): string {
  if (value === "insufficient_data") return t("admin.observedUnknown");
  return t("admin.user.mistakes");
}

function recommendationStatusLabel(value: string): string {
  if (value === "active" || value === "completed" || value === "shown" || value === "accepted") return t("admin.status.verified");
  if (value === "skipped") return t("feedback.skipped");
  return t("admin.unknown");
}

function evidenceLabel(value: string): string {
  if (value === "strong" || value === "direct") return t("admin.evidence.strong");
  if (value === "weak") return t("admin.evidence.weak");
  if (value === "positive") return t("admin.evidence.positive");
  if (value === "negative") return t("admin.evidence.negative");
  if (value === "neutral") return t("admin.evidence.neutral");
  return t("admin.unknown");
}

export function AdminExerciseDetailPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const tab: Tab = TABS.includes(requestedTab as Tab) ? requestedTab as Tab : "overview";
  const [exercise, setExercise] = useState<AdminExerciseDetail | null>(null);
  const [analytics, setAnalytics] = useState<AdminExerciseAnalyticsDetail | null>(null);
  const [quality, setQuality] = useState<ExerciseQuality | null>(null);
  const [learning, setLearning] = useState<ExerciseLearning | null>(null);
  const [generators, setGenerators] = useState<Generator[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    if (!slug) {
      setFailed(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    try {
      const [e, a, q, l, g] = await Promise.all([
        adminApi.exercise(slug),
        adminApi.exerciseAnalyticsDetail(slug, { period: "30d" }).catch(() => null),
        adminApi.exerciseQuality(slug).catch(() => null),
        adminApi.exerciseLearning(slug, 30).catch(() => null),
        adminApi.exerciseGenerators(slug).catch(() => []),
      ]);
      setExercise(e);
      setAnalytics(a);
      setQuality(q);
      setLearning(l);
      setGenerators(g);
      setLoading(false);
    } catch {
      setFailed(true);
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void load();
  }, [load]);

  function changeTab(next: Tab) {
    setSearchParams((current) => {
      const params = new URLSearchParams(current);
      if (next === "overview") params.delete("tab");
      else params.set("tab", next);
      return params;
    });
  }

  if (loading) {
    return (
      <>
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      </>
    );
  }
  if (failed || !exercise || !slug) {
    return (
      <>
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={() => void load()} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title={`${t("admin.workspace")}: ${exercise.title_fa}`} subtitle={exercise.description || t("admin.workspace")} />
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
        {TABS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => changeTab(key)}
            className={`min-h-[44px] shrink-0 rounded-full px-4 text-sm font-bold ${
              tab === key ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"
            }`}
          >
            {tabLabel(key)}
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <OverviewTab
          exercise={exercise}
          analytics={analytics}
          quality={quality}
          learning={learning}
          slug={slug}
          onTab={changeTab}
        />
      ) : null}
      {tab === "puzzles" ? <PuzzlesTab slug={slug} /> : null}
      {tab === "generate" ? <GenerateTab slug={slug} generators={generators} /> : null}
      {tab === "review" ? <ReviewTab slug={slug} /> : null}
      {tab === "quality" ? <QualityTab quality={quality} /> : null}
      {tab === "difficulty" ? <DifficultyTab quality={quality} analytics={analytics} /> : null}
      {tab === "learning" ? <LearningTab learning={learning} /> : null}
      {tab === "analytics" ? <AnalyticsTab analytics={analytics} /> : null}
      {tab === "settings" ? <SettingsTab exercise={exercise} onChanged={() => void load()} /> : null}
    </>
  );
}

function OverviewTab({
  exercise,
  analytics,
  quality,
  learning,
  slug,
  onTab,
}: {
  exercise: AdminExerciseDetail;
  analytics: AdminExerciseAnalyticsDetail | null;
  quality: ExerciseQuality | null;
  learning: ExerciseLearning | null;
  slug: string;
  onTab: (tab: Tab) => void;
}) {
  const draftCount =
    analytics?.supply_by_status.find((row) => row.status === "draft")?.count ?? null;
  return (
    <div className="flex flex-col gap-2">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-black">{exercise.title_fa}</h2>
             <p className="mt-1 text-xs text-stone-500" dir="ltr">
               {t("admin.label.exercise")}: {slug}
             </p>
            <p className="mt-1 text-sm text-stone-600">{exercise.description}</p>
          </div>
          <Badge>{exercise.is_active ? t("admin.statusEnabled") : t("admin.statusDisabled")}</Badge>
        </div>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Link
            to={`/admin/puzzles/new?exercise=${encodeURIComponent(slug)}`}
            className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
          >
            {t("admin.editor.addNew")}
          </Link>
          <Link
            to={`/admin/generators?exercise=${encodeURIComponent(slug)}`}
            className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-violet-100 px-4 text-sm font-bold text-violet-700"
          >
            {t("admin.runGenerator")}
          </Link>
        </div>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.puzzles")}</h2>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-5">
          <Stat value={faNum(exercise.puzzle_count)} label={t("admin.table.total")} />
          <Stat value={faNum(exercise.published_count)} label={t("admin.publishedCount")} />
          <Stat
            value={draftCount === null ? "—" : faNum(draftCount)}
            label={t("admin.statusDraft")}
          />
          <Stat value={faNum(exercise.needs_review_count)} label={t("admin.needsReview")} />
          <Stat
            value={quality ? supplyStateLabel(quality.supply_state) : "—"}
            label={t("admin.contentHealth")}
          />
        </div>
        {exercise.low_supply ? (
          <p className="mt-2 text-sm font-bold text-amber-700">{t("admin.lowSupply")}</p>
        ) : null}
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.lifecycleState")}</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge>{exercise.is_active ? t("admin.statusEnabled") : t("admin.statusDisabled")}</Badge>
          {quality?.supply_by_status.map((row) => (
            <span key={row.status} className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-700">
              {statusLabel(row.status)}: {faNum(row.count)}
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-sm font-bold text-violet-700">
          <Link to={`/admin/puzzles?exercise=${encodeURIComponent(slug)}`} className="inline-flex min-h-[44px] items-center">
            {t("admin.tabPuzzles")}
          </Link>
          <Link to={`/admin/review-queue?exercise=${encodeURIComponent(slug)}`} className="inline-flex min-h-[44px] items-center">
            {t("admin.tabReview")}
          </Link>
        </div>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.usageRecent")}</h2>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3">
          <Stat value={faNum(exercise.attempts_count)} label={t("admin.attempts")} />
          <Stat
            value={exercise.success_rate === null ? "—" : faPercent(exercise.success_rate)}
            label={t("admin.successRate")}
          />
          <Stat
            value={learning ? faNum(learning.usage.active_users) : "—"}
            label={t("admin.activeUsers")}
          />
        </div>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.learning")}</h2>
        {learning ? (
          <div className="mt-1 text-sm">
            <p>
              {t("admin.skillsPrimary")}: <b dir="ltr">{learning.skills.primary ?? "—"}</b>
            </p>
            <p className="mt-1 text-xs text-stone-500" dir="ltr">
              {learning.skills.secondary.map((s) => `${s.skill} (${s.link})`).join(" · ") || "—"}
            </p>
          </div>
        ) : (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        )}
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.contentHealth")}</h2>
        {quality ? (
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {quality.attention_reasons.length === 0 ? (
              <li className="text-emerald-700">{t("admin.supplyHealthy")}</li>
            ) : (
              quality.attention_reasons.map((reason) => (
                <li key={reason} className="font-bold text-amber-700">
                  {reasonLabel(reason)}
                </li>
              ))
            )}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        )}
        <Button variant="secondary" onClick={() => onTab("quality")} className="mt-2 w-full">
          {t("admin.details")}
        </Button>
      </Card>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl bg-stone-50 px-3 py-3 text-center">
      <p className="text-xl font-black text-violet-700">{value}</p>
      <p className="mt-1 text-xs text-stone-500">{label}</p>
    </div>
  );
}

function PuzzlesTab({ slug }: { slug: string }) {
  return (
    <Card>
      <h2 className="font-black">{t("admin.puzzles")}</h2>
      <p className="mt-1 text-sm text-stone-500">{t("admin.lifecycleHint")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/admin/puzzles?exercise=${encodeURIComponent(slug)}`}
          className="inline-flex min-h-[44px] items-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
        >
          {t("admin.puzzles")}
        </Link>
        <Link
          to={`/admin/puzzles/new?exercise=${encodeURIComponent(slug)}`}
          className="inline-flex min-h-[44px] items-center rounded-xl bg-violet-100 px-4 text-sm font-bold text-violet-700"
        >
          {t("admin.editor.addNew")}
        </Link>
      </div>
    </Card>
  );
}

function GenerateTab({ slug, generators }: { slug: string; generators: Generator[] }) {
  return (
    <Card>
      <h2 className="font-black">{t("admin.generateTitle")}</h2>
      <p className="mt-1 text-sm text-stone-500">{t("admin.generator.oneAtATime")}</p>
      {generators.length === 0 ? (
        <p className="mt-2 rounded-2xl bg-amber-50 p-3 text-sm font-bold text-amber-800">
          {t("admin.generator.exerciseMissing")}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/admin/generators?exercise=${encodeURIComponent(slug)}`}
          className="inline-flex min-h-[44px] items-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
        >
          {t("admin.runGenerator")}
        </Link>
        <Link
          to={`/admin/puzzles/new?exercise=${encodeURIComponent(slug)}`}
          className="inline-flex min-h-[44px] items-center rounded-xl bg-violet-100 px-4 text-sm font-bold text-violet-700"
        >
          {t("admin.editor.addNew")}
        </Link>
      </div>
    </Card>
  );
}

function ReviewTab({ slug }: { slug: string }) {
  return (
    <Card>
      <h2 className="font-black">{t("admin.reviewQueue")}</h2>
      <p className="mt-1 text-sm text-stone-500">{t("admin.reviewSubtitle")}</p>
      <Link
        to={`/admin/review-queue?exercise=${encodeURIComponent(slug)}`}
        className="mt-3 inline-flex min-h-[44px] items-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
      >
        {t("admin.reviewQueueOpen")}
      </Link>
    </Card>
  );
}

function QualityTab({ quality }: { quality: ExerciseQuality | null }) {
  if (!quality) {
    return (
      <Card>
        <p className="text-center text-stone-500">{t("admin.empty")}</p>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Card>
        <h2 className="font-black">{t("admin.contentHealth")}</h2>
        <p className="mt-1 font-black text-violet-700">{supplyStateLabel(quality.supply_state)}</p>
        <ul className="mt-1 flex flex-col gap-1 text-sm">
          {quality.attention_reasons.map((reason) => (
            <li key={reason} className="font-bold text-amber-700">
              {reasonLabel(reason)}
            </li>
          ))}
          {quality.attention_reasons.length === 0 ? (
            <li className="text-emerald-700">{t("admin.supplyHealthy")}</li>
          ) : null}
        </ul>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.supplyByStatus")}</h2>
        <ul className="mt-2 flex flex-col gap-1">
          {quality.supply_by_status.map((row) => (
            <li
              key={row.status}
              className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"
            >
              <span className="font-bold">{statusLabel(row.status)}</span>
              <span>{faNum(row.count)}</span>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.reviewQueue")}</h2>
        <div className="mt-2 grid grid-cols-3 gap-2 text-center">
          <Stat value={faNum(quality.review_backlog)} label={t("admin.needsReview")} />
          <Stat value={faNum(quality.quarantined)} label={t("admin.quarantine")} />
          <Stat value={faNum(quality.validation_failures)} label={t("admin.validationFailed")} />
        </div>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.repeatedFailures")}</h2>
        {quality.high_failure_puzzles.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {quality.high_failure_puzzles.map((row) => (
              <li key={row.puzzle_id}>
                <Link
                  to={`/admin/puzzles/${row.puzzle_id}`}
                  className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 text-sm font-bold text-violet-700"
                >
                  <span dir="ltr">#{row.puzzle_id}</span>
                  <span dir="ltr">
                    {faNum(row.attempts)} · {faPercent(1 - row.failure_rate)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function DifficultyTab({
  quality,
  analytics,
}: {
  quality: ExerciseQuality | null;
  analytics: AdminExerciseAnalyticsDetail | null;
}) {
  const dist = quality?.difficulty_distribution ?? [];
  const max = Math.max(1, ...dist.map((row) => row.count));
  const avgDeclared = dist.length
    ? dist.reduce((sum, row) => sum + (row.difficulty ?? 0) * row.count, 0) /
      Math.max(1, dist.reduce((sum, row) => sum + row.count, 0))
    : null;
  const success = quality?.success_rate ?? null;
  const attempts = quality?.attempts ?? 0;
  const differs =
    attempts >= 30 &&
    avgDeclared !== null &&
    success !== null &&
    ((success < 0.4 && avgDeclared <= 2) || (success > 0.85 && avgDeclared >= 4));
  return (
    <div className="flex flex-col gap-2">
      <Card>
        <h2 className="font-black">{t("admin.difficultyDist")}</h2>
        {dist.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {dist.map((row) => (
              <li key={String(row.difficulty)} className="flex items-center gap-2" dir="ltr">
                <span className="w-6 text-center font-black">{row.difficulty ?? "—"}</span>
                <div className="h-4 flex-1 overflow-hidden rounded bg-stone-100">
                  <div className="h-full rounded bg-violet-500" style={{ width: `${Math.round((row.count / max) * 100)}%` }} />
                </div>
                <span className="w-12 text-right text-sm">{faNum(row.count)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.declaredVsObserved")}</h2>
        <div className="mt-2 grid grid-cols-2 gap-2 text-center">
          <Stat value={avgDeclared === null ? "—" : avgDeclared.toFixed(1)} label={t("admin.difficulty")} />
          <Stat value={success === null ? "—" : faPercent(success)} label={t("admin.successRate")} />
        </div>
        {differs ? (
          <p className="mt-2 text-sm font-bold text-amber-700">{t("admin.observedDiffers")}</p>
        ) : null}
        <p className="mt-1 text-xs text-stone-500">
          {t("admin.attempts")}: {faNum(attempts)}
          {analytics ? ` · ${t("admin.avgDuration")}: ${analytics.avg_response_ms === null ? t("admin.notAvailable") : `${faNum(Math.round(analytics.avg_response_ms / 1000))} ${t("common.seconds")}`}` : ""}
        </p>
      </Card>
    </div>
  );
}

function LearningTab({ learning }: { learning: ExerciseLearning | null }) {
  if (!learning) {
    return (
      <Card>
        <p className="text-center text-stone-500">{t("admin.empty")}</p>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Card>
        <h2 className="font-black">{t("admin.usageRecent")} ({faNum(learning.window_days)} {t("analytics.activeDays")})</h2>
        <div className="mt-2 grid grid-cols-2 gap-2 text-center md:grid-cols-4">
          <Stat value={faNum(learning.usage.attempts)} label={t("admin.attempts")} />
          <Stat
            value={learning.usage.success_rate === null ? "—" : faPercent(learning.usage.success_rate)}
            label={t("admin.successRate")}
          />
          <Stat value={faNum(learning.usage.active_users)} label={t("admin.activeUsers")} />
          <Stat
             value={learning.usage.avg_duration_ms === null ? t("admin.notAvailable") : `${faNum(Math.round(learning.usage.avg_duration_ms / 1000))} ${t("common.seconds")}`}
            label={t("admin.avgDuration")}
          />
        </div>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.mistakesCommon")}</h2>
        {learning.mistakes.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {learning.mistakes.map((row) => (
              <li
                key={row.mistake}
                className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"
              >
                <span className="font-bold">{metricLabel(row.mistake)}</span>
                <span>{faNum(row.count)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.skillsPrimary")} / {t("admin.skillsSecondary")}</h2>
        <p className="mt-1 text-sm">
          {t("admin.skillsPrimary")}: <b dir="ltr">{learning.skills.primary ?? "—"}</b>
        </p>
        <p className="mt-1 text-xs text-stone-500" dir="ltr">
          {learning.skills.secondary.map((s) => `${s.skill} (${s.link})`).join(" · ") || "—"}
        </p>
        {learning.skills.evidence.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-1">
            {learning.skills.evidence.slice(0, 10).map((row, index) => (
              <li
                key={`${row.skill_key}-${row.direction}-${index}`}
                className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 text-sm"
              >
                <span dir="ltr">
                  {row.skill_key} · {evidenceLabel(row.direction)}
                </span>
                <span>{faNum(row.count)}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="mt-1 text-xs text-stone-500">{t("admin.masteryNote")}</p>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.recommendations")}</h2>
        {learning.recommendations.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <p className="mt-1 text-xs text-stone-500" dir="ltr">
            {learning.recommendations.map((r) => `${recommendationStatusLabel(r.status)}=${faNum(r.count)}`).join(" · ")}
          </p>
        )}
      </Card>
    </div>
  );
}

function AnalyticsTab({ analytics }: { analytics: AdminExerciseAnalyticsDetail | null }) {
  if (!analytics) {
    return (
      <Card>
        <p className="text-center text-stone-500">{t("admin.empty")}</p>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat value={faNum(analytics.attempts)} label={t("admin.attempts")} />
        <Stat value={faNum(analytics.unique_players)} label={t("admin.uniquePlayers")} />
        <Stat value={faPercent(analytics.accuracy)} label={t("player.accuracy")} />
        <Stat value={faNum(analytics.current_ratings)} label={t("admin.ratedPlayers")} />
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
            <li
              key={row.status}
              className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"
            >
              <span className="font-bold">{statusLabel(row.status)}</span>
              <span>{faNum(row.count)}</span>
            </li>
          ))}
          {analytics.supply_by_status.length === 0 && (
            <p className="text-sm text-stone-500">{t("admin.empty")}</p>
          )}
        </ul>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.difficultyDist")}</h2>
        <ul className="mt-2 flex flex-col gap-1">
          {analytics.difficulty_distribution.map((row) => (
            <li
              key={String(row.difficulty)}
              className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"
            >
              <span dir="ltr" className="font-bold">
                {String(row.difficulty ?? "—")}
              </span>
              <span>{faNum(row.count)}</span>
            </li>
          ))}
          {analytics.difficulty_distribution.length === 0 && (
            <p className="text-sm text-stone-500">{t("admin.empty")}</p>
          )}
        </ul>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.mistakeDist")}</h2>        <ul className="mt-2 flex flex-col gap-1">
          {analytics.mistake_distribution.map((row) => (
            <li
              key={row.mistake}
              className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3"
            >
               <span className="font-bold">{metricLabel(row.mistake)}</span>
              <span>{faNum(row.count)}</span>
            </li>
          ))}
          {analytics.mistake_distribution.length === 0 && (
            <p className="text-sm text-stone-500">{t("admin.empty")}</p>
          )}
        </ul>
      </Card>
      <Card>
        <h2 className="font-black">{t("admin.recommendationOutcomes")}</h2>
        {analytics.recommendation_outcomes.length === 0 ? (
          <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <p className="mt-1 text-xs text-stone-500" dir="ltr">
            {analytics.recommendation_outcomes.map((r) => `${recommendationStatusLabel(r.status)}=${faNum(r.count)}`).join(" · ")}
          </p>
        )}
      </Card>
    </div>
  );
}

function SettingsTab({
  exercise,
  onChanged,
}: {
  exercise: AdminExerciseDetail;
  onChanged: () => void;
}) {
  const [title, setTitle] = useState(exercise.title_fa);
  const [titleEn, setTitleEn] = useState(exercise.title_en);
  const [description, setDescription] = useState(exercise.description);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setTitle(exercise.title_fa);
    setTitleEn(exercise.title_en);
    setDescription(exercise.description);
  }, [exercise.slug, exercise.title_fa, exercise.title_en, exercise.description]);

  async function save() {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.updateExercise(exercise.slug, {
        title_fa: title,
        title_en: titleEn,
        description,
      });
      onChanged();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(next: boolean) {
    if (!next && !window.confirm(t("admin.disableConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.updateExercise(exercise.slug, { is_active: next });
      onChanged();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Card>
        <p className="text-xs text-stone-500">
          {t("admin.exerciseSlug")}: <b dir="ltr">{exercise.slug}</b>
        </p>
        <label className="mt-2 block text-sm font-bold" htmlFor="ex-title">
          {t("admin.exerciseDetail")}
        </label>
        <input
          id="ex-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
        />
        <label className="mt-2 block text-sm font-bold" htmlFor="ex-title-en">
           {t("admin.exerciseEnglishTitle")}
        </label>
        <input
          id="ex-title-en"
          dir="ltr"
          value={titleEn}
          onChange={(e) => setTitleEn(e.target.value)}
          className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
        />
        <label className="mt-2 block text-sm font-bold" htmlFor="ex-desc">
          {t("admin.explanation")}
        </label>
        <textarea
          id="ex-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
        />
        {notice ? <p className="mt-1 text-sm font-bold text-red-600">{notice}</p> : null}
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Button disabled={busy} onClick={() => void save()}>
            {t("profile.save")}
          </Button>
          {exercise.is_active ? (
            <Button disabled={busy} variant="secondary" onClick={() => void toggle(false)}>
              {t("admin.disable")}
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => void toggle(true)}>
              {t("admin.enable")}
            </Button>
          )}
        </div>
        <p className="mt-2 text-xs text-stone-500">{t("admin.updatedNote")}</p>
      </Card>
    </div>
  );
}
