import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type {
  AdminExercise,
  AdminPuzzle,
  AnswerContract,
  Generator,
  GeneratorRun,
  PreviewValidation,
} from "../api/types";
import { ChessBoard } from "../components/chess/ChessBoard";
import { AnswerEditor, answerSummary } from "../components/content/AnswerEditor";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";
import { faNum } from "../lib/playerDisplay";

const RUN_PAGE_SIZE = 10;

interface CandidateState {
  puzzle: AdminPuzzle;
  contract: AnswerContract | null;
  validation: PreviewValidation | null;
}

function statusLabel(status: string): string {
  if (status === "draft") return t("admin.statusDraft");
  if (status === "validated") return t("admin.statusValidated");
  if (status === "reviewed") return t("admin.statusReviewed");
  if (status === "approved") return t("admin.statusApproved");
  if (status === "published") return t("admin.statusPublished");
  if (status === "quarantined") return t("admin.status.quarantined");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "retired") return t("admin.status.retired");
  if (status === "queued") return t("admin.status.pending");
  if (status === "running") return t("admin.status.running");
  if (status === "completed") return t("admin.status.verified");
  if (status === "failed") return t("admin.status.failed");
  if (status === "cancelled") return t("admin.status.cancelled");
  return t("admin.unknown");
}

function sourceLabel(source: string): string {
  if (source === "manual") return t("admin.sourceManual");
  if (source === "generated") return t("admin.sourceGenerated");
  if (source === "imported") return t("admin.sourceImported");
  return t("admin.unknown");
}

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function AdminGeneratorsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialExercise = searchParams.get("exercise") ?? "";
  const [generators, setGenerators] = useState<Generator[]>([]);
  const [exercises, setExercises] = useState<AdminExercise[]>([]);
  const [exerciseSlug, setExerciseSlug] = useState(initialExercise);
  const [runs, setRuns] = useState<GeneratorRun[]>([]);
  const [runTotal, setRunTotal] = useState(0);
  const [runPage, setRunPage] = useState(1);
  const [run, setRun] = useState<GeneratorRun | null>(null);
  const [candidate, setCandidate] = useState<CandidateState | null>(null);
  const [seed, setSeed] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [targetRating, setTargetRating] = useState("");
  const [reason, setReason] = useState("");
  const [acceptedCount, setAcceptedCount] = useState(0);
  const [rejectedCount, setRejectedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const fetchRuns = useCallback(async (exercise: string, page: number) => {
    const params = { exercise: exercise || undefined, page, page_size: RUN_PAGE_SIZE };
    const loader = typeof adminApi.generatorRunsPage === "function"
      ? adminApi.generatorRunsPage
      : adminApi.generatorRuns;
    const response = await loader(params);
    if (Array.isArray(response)) return { items: response, total: response.length };
    return response;
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    Promise.all([
      adminApi.generators(),
      adminApi.exercises().catch(() => []),
      fetchRuns(initialExercise, 1).catch(() => ({ items: [], total: 0 })),
    ])
      .then(([registry, catalog, history]) => {
        if (!active) return;
        setGenerators(registry);
        setExercises(catalog);
        setRuns(history.items);
        setRunTotal(history.total);
        setExerciseSlug((current) => {
          if (current) return current;
          if (initialExercise) return initialExercise;
          return registry[0]?.exercise_slug ?? catalog[0]?.slug ?? "";
        });
        setInitialized(true);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setFailed(true);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchRuns, initialExercise]);

  useEffect(() => {
    if (!initialized) return;
    let active = true;
    setHistoryLoading(true);
    fetchRuns(exerciseSlug, runPage)
      .then((result) => {
        if (!active) return;
        setRuns(result.items);
        setRunTotal(result.total);
      })
      .catch(() => {
        if (active) setNotice(t("common.error"));
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });
    return () => {
      active = false;
    };
  }, [exerciseSlug, fetchRuns, initialized, runPage]);

  const availableGenerators = useMemo(
    () => generators.filter((generator) => generator.exercise_slug === exerciseSlug),
    [exerciseSlug, generators],
  );
  const selectedGenerator = availableGenerators[0] ?? null;
  const supportedSlugs = new Set(generators.map((generator) => generator.exercise_slug));
  const unsupported = exercises.filter((exercise) => !supportedSlugs.has(exercise.slug));
  const runPages = Math.max(1, Math.ceil(runTotal / RUN_PAGE_SIZE));
  useEffect(() => {
    if (runPage > runPages) setRunPage(runPages);
  }, [runPage, runPages]);

  function chooseExercise(slug: string) {
    setExerciseSlug(slug);
    setRunPage(1);
    setRun(null);
    setCandidate(null);
    setNotice("");
    setSearchParams(slug ? { exercise: slug } : {});
  }

  async function refreshHistory() {
    try {
      const result = await fetchRuns(exerciseSlug, runPage);
      setRuns(result.items);
      setRunTotal(result.total);
    } catch {
      setNotice(t("common.error"));
    }
  }

  function optionalInteger(raw: string): number | undefined {
    if (raw.trim() === "") return undefined;
    const value = Number(raw);
    return Number.isInteger(value) ? value : undefined;
  }

  function optionalNumber(raw: string): number | undefined {
    if (raw.trim() === "") return undefined;
    const value = Number(raw);
    return Number.isFinite(value) ? value : undefined;
  }

  async function createCandidate(automaticSeed: boolean) {
    if (!selectedGenerator) return;
    const seedValue = optionalInteger(seed);
    const difficultyValue = optionalInteger(difficulty);
    const targetValue = optionalNumber(targetRating);
    if (seed.trim() !== "" && seedValue === undefined) {
      setNotice(t("admin.generateSeed"));
      return;
    }
    if (difficulty.trim() !== "" && (difficultyValue === undefined || difficultyValue < 1 || difficultyValue > 5)) {
      setNotice(t("admin.difficultyHint"));
      return;
    }
    if (targetValue !== undefined && (targetValue < 100 || targetValue > 3000)) {
      setNotice(t("admin.ratingHint"));
      return;
    }
    setNotice("");
    const job = await adminApi.runGenerator(selectedGenerator.code, {
      count: 1,
      seed: automaticSeed ? undefined : seedValue,
      target_rating: targetValue,
      difficulty: difficultyValue,
      config: {},
    });
    setRun(job);
    setSeed("");
    const candidateId = job.result.accepted_puzzle_ids?.[0] ?? null;
    if (candidateId === null) {
      setCandidate(null);
      await refreshHistory();
      return;
    }
    const puzzle = await adminApi.puzzle(candidateId);
    const contract = await adminApi.answerContract(puzzle.exercise_slug).catch(() => null);
    const validation = await adminApi.previewValidate({
      exercise_slug: puzzle.exercise_slug,
      fen: puzzle.fen,
      position_json: puzzle.position_json,
      answer_json: puzzle.answer_json,
      difficulty: puzzle.difficulty,
      target_rating: puzzle.target_rating,
      initial_rating: puzzle.initial_rating,
      prompt_fa: puzzle.prompt_fa,
      explanation: puzzle.explanation,
      exclude_puzzle_id: puzzle.id,
    }).catch(() => null);
    setCandidate({ puzzle, contract, validation });
    await refreshHistory();
  }

  async function generateNext() {
    if (!selectedGenerator || busy) return;
    setBusy(true);
    try {
      await createCandidate(false);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function acceptCandidate() {
    if (!candidate || !["draft", "validated"].includes(candidate.puzzle.status) || busy) return;
    setBusy(true);
    setNotice("");
    try {
      const validated = await adminApi.validatePuzzle(candidate.puzzle.id);
      if (validated.status !== "validated") {
        setCandidate((current) => current ? { ...current, puzzle: validated } : current);
        setNotice(t("admin.generator.validationRequired"));
        return;
      }
      const reviewed = await adminApi.reviewPuzzle(validated.id, { decision: "approve", notes: "" });
      if (reviewed.status !== "reviewed") throw new Error("review_not_completed");
      setAcceptedCount((count) => count + 1);
      setCandidate(null);
      setRun(null);
      setReason("");
      await refreshHistory();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function rejectCandidate() {
    if (!candidate || !reason.trim() || busy) return;
    if (!window.confirm(t("admin.generator.rejectNote"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.rejectPuzzle(candidate.puzzle.id, reason.trim());
      setRejectedCount((count) => count + 1);
      setCandidate(null);
      setRun(null);
      setReason("");
      await refreshHistory();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function regenerateCandidate() {
    if (!candidate || !reason.trim() || busy) return;
    if (!window.confirm(t("admin.generator.rejectNote"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.rejectPuzzle(candidate.puzzle.id, reason.trim());
      setRejectedCount((count) => count + 1);
      setCandidate(null);
      setRun(null);
      setReason("");
      await createCandidate(true);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const exerciseOptions: Array<Pick<AdminExercise, "slug" | "title_fa">> = exercises.some((exercise) => exercise.slug === exerciseSlug)
    ? exercises
    : exerciseSlug
      ? [{ slug: exerciseSlug, title_fa: exerciseSlug }, ...exercises]
      : exercises;

  return (
    <div className="flex flex-col gap-2">
      <PageHeader title={t("admin.generators")} subtitle={t("admin.subtitle")} />

      <Card>
        <h2 className="font-black">{t("admin.generateTitle")}</h2>
        <p className="mt-1 text-sm text-stone-500">{t("admin.generator.oneAtATime")}</p>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          <label className="text-sm font-bold" htmlFor="generator-exercise">
            {t("admin.label.exercise")}
            <select
              id="generator-exercise"
              value={exerciseSlug}
              onChange={(event) => chooseExercise(event.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal"
            >
              <option value="">{t("admin.all")}</option>
              {exerciseOptions.map((exercise) => (
                <option key={exercise.slug} value={exercise.slug}>{exercise.title_fa} · {exercise.slug}</option>
              ))}
            </select>
          </label>
          <div>
            <p className="text-sm font-bold">{t("admin.generators")}</p>
            <p className="mt-2 min-h-[44px] rounded-xl bg-stone-50 px-3 py-3 font-mono text-sm" dir="ltr">
              {selectedGenerator ? `${selectedGenerator.code} · ${selectedGenerator.version}` : "—"}
            </p>
          </div>
        </div>

        {exerciseSlug && !selectedGenerator ? (
          <div className="mt-3 rounded-2xl bg-amber-50 p-3">
            <p className="text-sm font-bold text-amber-800">{t("admin.generator.exerciseMissing")}</p>
            <Link
              to={`/admin/puzzles/new?exercise=${encodeURIComponent(exerciseSlug)}`}
              className="mt-2 inline-flex min-h-[44px] items-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
            >
              {t("admin.editor.addNew")}
            </Link>
          </div>
        ) : null}

        {selectedGenerator ? (
          <>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
              <label className="text-sm font-bold" htmlFor="generator-seed">
                {t("admin.generateSeed")}
                <input
                  id="generator-seed"
                  value={seed}
                  inputMode="numeric"
                  onChange={(event) => setSeed(event.target.value)}
                  className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm font-normal"
                  dir="ltr"
                />
              </label>
              <label className="text-sm font-bold" htmlFor="generator-difficulty">
                {t("admin.difficulty")}
                <input
                  id="generator-difficulty"
                  value={difficulty}
                  inputMode="numeric"
                  onChange={(event) => setDifficulty(event.target.value)}
                  className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm font-normal"
                  dir="ltr"
                />
              </label>
              <label className="text-sm font-bold" htmlFor="generator-rating">
                {t("admin.targetRating")}
                <input
                  id="generator-rating"
                  value={targetRating}
                  inputMode="decimal"
                  onChange={(event) => setTargetRating(event.target.value)}
                  className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm font-normal"
                  dir="ltr"
                />
              </label>
            </div>
            <p className="mt-2 text-xs text-stone-500">{t("admin.generator.suggestedMeaning")}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-2xl bg-emerald-50 p-3 text-center">
                <p className="text-xl font-black text-emerald-700">{faNum(acceptedCount)}</p>
                <p className="text-xs text-stone-600">{t("admin.generator.acceptedCount")}</p>
              </div>
              <div className="rounded-2xl bg-red-50 p-3 text-center">
                <p className="text-xl font-black text-red-700">{faNum(rejectedCount)}</p>
                <p className="text-xs text-stone-600">{t("admin.generator.rejectedCount")}</p>
              </div>
            </div>
            {!candidate ? (
              <Button disabled={busy} onClick={() => void generateNext()} className="mt-3 w-full">
                {t("admin.generator.generateNext")}
              </Button>
            ) : null}
          </>
        ) : null}
        {notice ? <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}
      </Card>

      {candidate ? (
        <Card>
           <div className="flex flex-wrap items-center justify-between gap-2">
             <h2 className="font-black">{t("admin.generator.candidate")}</h2>
             <div className="flex items-center gap-2">
               <Link
                 to={`/admin/puzzles/${candidate.puzzle.id}/edit`}
                 className="inline-flex min-h-[44px] items-center text-sm font-bold text-violet-700"
               >
                 {t("admin.editPuzzle")}
               </Link>
               <Badge>{statusLabel(candidate.puzzle.status)}</Badge>
             </div>
           </div>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div>
              {candidate.puzzle.fen ? (
                <div dir="ltr" className="mx-auto max-w-sm">
                  <ChessBoard pieces={fenToPieces(candidate.puzzle.fen)} disabled />
                </div>
              ) : (
                <div className="rounded-2xl bg-stone-50 p-4 text-center text-sm text-stone-500">{t("admin.empty")}</div>
              )}
              <p className="mt-2 text-sm font-bold">{t("admin.promptFa")}</p>
              <p className="mt-1">{candidate.puzzle.prompt_fa || t("admin.empty")}</p>
              <p className="mt-3 text-sm font-bold">{t("admin.explanation")}</p>
              <p className="mt-1 text-sm text-stone-600">{candidate.puzzle.explanation || t("admin.empty")}</p>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <h3 className="font-black">{t("admin.review.answer")}</h3>
                {candidate.contract ? (
                  <div className="mt-2 rounded-2xl bg-stone-50 p-3">
                    <AnswerEditor
                      contract={candidate.contract}
                      answer={candidate.puzzle.answer_json}
                      onChange={() => undefined}
                      disabled
                    />
                  </div>
                ) : (
                  <p className="mt-2 break-all font-mono text-xs" dir="ltr">{answerSummary(candidate.puzzle.answer_json)}</p>
                )}
              </div>
              <div>
                <h3 className="font-black">{t("admin.generator.suggestedMeaning")}</h3>
                <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.difficulty")}</dt>
                    <dd dir="ltr">{candidate.puzzle.difficulty ?? "—"}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.targetRating")}</dt>
                    <dd dir="ltr">{candidate.puzzle.target_rating ?? "—"}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.rating")}</dt>
                    <dd dir="ltr">{faNum(candidate.puzzle.initial_rating)}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.status")}</dt>
                    <dd>{statusLabel(candidate.puzzle.status)}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-2xl bg-stone-50 p-3 text-sm">
            <h3 className="font-black">{t("admin.runDetail")}</h3>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-xs text-stone-500">{t("admin.label.source")}</dt>
                <dd>{sourceLabel(candidate.puzzle.source)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.editor.sourceReference")}</dt>
                <dd className="break-all" dir="ltr">{candidate.puzzle.source_reference || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.generatorRuns")}</dt>
                <dd dir="ltr">{candidate.puzzle.generator_run_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.review.created")}</dt>
                <dd dir="ltr">{formatDate(candidate.puzzle.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.label.user")}</dt>
                <dd dir="ltr">{run?.requested_by_user_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.seed")}</dt>
                <dd dir="ltr">{run?.seed ?? "—"}</dd>
              </div>
            </dl>
          </div>

          <div className="mt-3 rounded-2xl border border-stone-200 p-3">
            <h3 className="font-black">{t("admin.review.validation")}</h3>
            {candidate.validation ? (
              <p className={`mt-1 text-sm font-bold ${candidate.validation.ok ? "text-emerald-700" : "text-red-600"}`}>
                {candidate.validation.ok ? t("admin.validationPassed") : t("admin.validationFailed")}
              </p>
            ) : (
              <p className="mt-1 text-sm text-stone-500">{statusLabel(candidate.puzzle.status)}</p>
            )}
             {candidate.validation && candidate.validation.errors.length > 0 ? (
               <p className="mt-1 text-xs text-red-600">
                 {t("admin.editor.validationErrorsCount").replace("{count}", faNum(candidate.validation.errors.length))}
               </p>
             ) : null}
          </div>

          <p className="mt-3 text-xs text-stone-500">{t("admin.generator.acceptNote")}</p>
          <p className="mt-1 text-xs text-stone-500">{t("admin.generator.rejectNote")}</p>
          <label className="mt-3 block text-sm font-bold" htmlFor="generator-reason">
            {t("admin.label.reason")}
          </label>
          <input
            id="generator-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("admin.label.reason")}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <Button
              disabled={busy || !["draft", "validated"].includes(candidate.puzzle.status)}
              onClick={() => void acceptCandidate()}
            >
              {t("admin.generator.accept")}
            </Button>
            <Button
              disabled={busy || !reason.trim()}
              variant="secondary"
              onClick={() => void rejectCandidate()}
            >
              {t("admin.generator.reject")}
            </Button>
            <Button
              disabled={busy || !reason.trim()}
              variant="secondary"
              onClick={() => void regenerateCandidate()}
            >
              {t("admin.generator.regenerate")}
            </Button>
          </div>
        </Card>
      ) : run ? (
        <Card>
          <h2 className="font-black">{t("admin.generateResult")}</h2>
          <p className="mt-1 text-sm">
            {t("admin.label.status")}: {statusLabel(run.status)} · {t("admin.accepted")}: {faNum(run.accepted_count)} ·{" "}
            {t("admin.rejected")}: {faNum(run.rejected_count)}
          </p>
           {run.result.rejected && run.result.rejected.length > 0 ? (
             <p className="mt-2 text-xs text-red-600">
               {t("admin.generator.failedCandidates").replace("{count}", faNum(run.result.rejected.length))}
             </p>
           ) : null}
           {run.error ? <p className="mt-2 text-sm font-bold text-red-600">{t("common.error")}</p> : null}
        </Card>
      ) : (
        <Card><p className="text-center text-stone-500">{t("admin.generator.noCandidate")}</p></Card>
      )}

      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <Card>
          <h2 className="font-black">{t("admin.generatorsSupported")}</h2>
          {generators.length === 0 ? (
            <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-1 text-sm">
              {generators.map((generator) => (
                <li key={generator.code} className="rounded-xl bg-stone-50 px-3 py-2" dir="ltr">
                  {generator.code} · {generator.exercise_slug} · {generator.version}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.generatorsUnsupported")}</h2>
          <p className="mt-1 text-xs text-stone-500">{t("admin.generatorUnsupportedNote")}</p>
          {unsupported.length === 0 ? (
            <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-1 text-sm">
              {unsupported.map((exercise) => (
                <li key={exercise.slug} className="rounded-xl bg-stone-50 px-3 py-2">
                  {exercise.title_fa} <span dir="ltr">· {exercise.slug}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-black">{t("admin.generatorRuns")}</h2>
          <span className="text-sm text-stone-500">{t("admin.table.total")}: {faNum(runTotal)}</span>
        </div>
        {historyLoading ? (
          <p className="mt-3 text-sm text-stone-500">{t("common.loading")}</p>
        ) : runs.length === 0 ? (
          <p className="mt-3 text-sm text-stone-500">{t("admin.empty")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {runs.map((item) => (
              <li key={item.id} className="rounded-2xl bg-stone-50 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold" dir="ltr">#{item.id} · {item.generator_code}</span>
                   <span className="flex items-center gap-2"><Badge>{statusLabel(item.status)}</Badge></span>
                </div>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.accepted")}: {faNum(item.accepted_count)} · {t("admin.rejected")}: {faNum(item.rejected_count)} ·{" "}
                  {t("admin.seed")}: <span dir="ltr">{item.seed ?? "—"}</span>
                </p>
                 {item.error ? <p className="mt-1 text-xs font-bold text-red-600">{t("common.error")}</p> : null}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex items-center justify-between gap-2">
          <Button variant="secondary" disabled={runPage <= 1} onClick={() => setRunPage((page) => Math.max(1, page - 1))}>
            {t("admin.pagination.previous")}
          </Button>
          <span className="text-center text-xs font-bold">
            {t("admin.pagination.summary")
              .replace("{page}", faNum(runPage))
              .replace("{pages}", faNum(runPages))
              .replace("{total}", faNum(runTotal))}
          </span>
          <Button variant="secondary" disabled={runPage >= runPages} onClick={() => setRunPage((page) => Math.min(runPages, page + 1))}>
            {t("admin.pagination.next")}
          </Button>
        </div>
      </Card>

      {loading ? (
        <Card><p className="text-center text-stone-500">{t("common.loading")}</p></Card>
      ) : failed ? (
        <Card>
          <p className="text-center text-stone-500">{t("common.error")}</p>
          <Button onClick={() => window.location.reload()} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </Card>
      ) : null}
    </div>
  );
}
