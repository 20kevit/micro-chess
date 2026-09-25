import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type {
  AdminPuzzle,
  AnswerContract,
  PreviewValidation,
  PuzzleHistory,
  PuzzleUsage,
} from "../api/types";
import { ChessBoard } from "../components/chess/ChessBoard";
import { AnswerEditor, answerSummary } from "../components/content/AnswerEditor";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";
import { faNum, faPercent } from "../lib/playerDisplay";

const MEANING_LOCKED = new Set(["published", "retired", "archived", "rejected", "quarantined"]);
const METADATA_LOCKED = new Set(["retired", "archived", "rejected", "quarantined"]);

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

function sourceLabel(source: string): string {
  if (source === "manual") return t("admin.sourceManual");
  if (source === "generated") return t("admin.sourceGenerated");
  if (source === "imported") return t("admin.sourceImported");
  return t("admin.unknown");
}

function validationLabel(status: string): string {
  if (status === "pass") return t("admin.validationPassed");
  if (status === "fail") return t("admin.validationFailed");
  return t("admin.unknown");
}

function reviewLabel(decision: string): string {
  if (decision === "approve") return t("admin.reviewApprove");
  if (decision === "request_changes") return t("admin.reviewRequestChanges");
  if (decision === "reject") return t("admin.reject");
  return t("admin.unknown");
}

function resultLabel(result: string): string {
  if (result === "correct") return t("feedback.correct");
  if (result === "partial") return t("feedback.partial");
  if (result === "wrong") return t("feedback.wrong");
  if (result === "timeout") return t("feedback.timeout");
  if (result === "skipped") return t("feedback.skipped");
  if (result === "abandoned") return t("feedback.abandoned");
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

interface HistoryEvent {
  id: string;
  at: string;
  title: string;
  actor: number | null;
  reason: string;
  technical: string;
}

function historyEvents(history: PuzzleHistory): HistoryEvent[] {
  const events: HistoryEvent[] = [];
  for (const row of history.transitions) {
    events.push({
      id: `transition-${row.id}`,
      at: row.created_at,
      title: `${statusLabel(row.from_status)} ← ${statusLabel(row.to_status)}`,
      actor: row.changed_by_user_id,
      reason: row.reason,
      technical: row.to_status,
    });
  }
  for (const row of history.validations) {
    const errorCount = Array.isArray(row.result.errors) ? row.result.errors.length : 0;
    const errors = errorCount > 0 ? t("admin.editor.validationErrorsCount").replace("{count}", faNum(errorCount)) : "";
    events.push({
      id: `validation-${row.id}`,
      at: row.created_at,
      title: `${t("admin.validationState")}: ${validationLabel(row.status)}`,
      actor: row.validated_by_user_id,
      reason: errors,
      technical: `v${row.validator_version} · ${row.status}`,
    });
  }
  for (const row of history.reviews) {
    events.push({
      id: `review-${row.id}`,
      at: row.created_at,
       title: `${t("admin.reviewDecision")}: ${reviewLabel(row.decision)}`,
      actor: row.reviewer_user_id,
      reason: row.notes,
      technical: row.decision,
    });
  }
  return events.sort((left, right) => left.at.localeCompare(right.at));
}

export function AdminPuzzleDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const puzzleId = Number(id);
  const [puzzle, setPuzzle] = useState<AdminPuzzle | null>(null);
  const [history, setHistory] = useState<PuzzleHistory | null>(null);
  const [usage, setUsage] = useState<PuzzleUsage | null>(null);
  const [contract, setContract] = useState<AnswerContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [rating, setRating] = useState("");
  const [preview, setPreview] = useState<PreviewValidation | null>(null);

  const load = useCallback(async () => {
    if (!Number.isInteger(puzzleId) || puzzleId <= 0) {
      setFailed(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    try {
      const row = await adminApi.puzzle(puzzleId);
      const [nextHistory, nextUsage, nextContract] = await Promise.all([
        adminApi.puzzleHistory(puzzleId).catch(() => null),
        adminApi.puzzleUsage(puzzleId).catch(() => null),
        adminApi.answerContract(row.exercise_slug).catch(() => null),
      ]);
      setPuzzle(row);
      setHistory(nextHistory);
      setUsage(nextUsage);
      setContract(nextContract);
      setDifficulty(row.difficulty === null || row.difficulty === undefined ? "" : String(row.difficulty));
      setRating(String(row.initial_rating ?? 1200));
      setLoading(false);
    } catch {
      setFailed(true);
      setLoading(false);
    }
  }, [puzzleId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<AdminPuzzle>) {
    if (!puzzle) return;
    setBusy(true);
    setNotice("");
    try {
      const row = await fn();
      setPuzzle(row);
      setDifficulty(row.difficulty === null || row.difficulty === undefined ? "" : String(row.difficulty));
      setRating(String(row.initial_rating ?? 1200));
      const [nextHistory, nextUsage] = await Promise.all([
        adminApi.puzzleHistory(row.id).catch(() => null),
        adminApi.puzzleUsage(row.id).catch(() => null),
      ]);
      setHistory(nextHistory);
      setUsage(nextUsage);
      setPreview(null);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveMeta() {
    if (!puzzle) return;
    const level = difficulty.trim() === "" ? null : Number(difficulty);
    if (level !== null && (!Number.isInteger(level) || level < 1 || level > 5)) {
      setNotice(t("admin.difficultyHint"));
      return;
    }
    const numeric = Number(rating);
    if (!Number.isFinite(numeric) || numeric < 100 || numeric > 3000) {
      setNotice(t("admin.ratingHint"));
      return;
    }
    await act(() => adminApi.updatePuzzle(puzzle.id, {
      difficulty: level,
      initial_rating: numeric,
    }));
  }

  async function onPreview() {
    if (!puzzle) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await adminApi.previewValidate({
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
      });
      setPreview(result);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function confirmLifecycle(message: string, action: () => void) {
    if (window.confirm(message)) action();
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !puzzle) {
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <Button onClick={() => void load()} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
      </div>
    );
  }

  const meaningLocked = MEANING_LOCKED.has(puzzle.status);
  const metadataLocked = METADATA_LOCKED.has(puzzle.status);
  const lastValidation = history?.validations[history.validations.length - 1] ?? null;
  const timeline = history ? historyEvents(history) : [];
  const visibility = puzzle.is_published
    ? t("admin.statusPublished")
    : puzzle.is_archived
      ? t("admin.statusArchived")
      : t("admin.editor.saveDraftNote");

  return (
    <>
      <PageHeader title={t("admin.puzzleDetail")} subtitle={t("admin.lifecycleState")} />
      <div className="mb-2 flex flex-wrap items-center gap-3 text-sm font-bold text-violet-700">
        <Link to={`/admin/exercises/${puzzle.exercise_slug}`}>{t("admin.backToExercise")}</Link>
        <Link to="/admin/puzzles">{t("admin.backToPuzzles")}</Link>
        {!meaningLocked ? (
          <button type="button" onClick={() => navigate(`/admin/puzzles/${puzzle.id}/edit`)}>
            {t("admin.editPuzzle")}
          </button>
        ) : null}
      </div>
      {notice ? <p className="mb-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}

      <div className="flex flex-col gap-2">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-black" dir="ltr">#{puzzle.id} · {puzzle.exercise_slug}</p>
              <p className="mt-1">{puzzle.prompt_fa || t("admin.empty")}</p>
            </div>
            <Badge>{statusLabel(puzzle.status)}</Badge>
          </div>
          <p className="mt-2 text-xs text-stone-500">{visibility}</p>
          {puzzle.explanation ? <p className="mt-2 text-sm text-stone-600">{puzzle.explanation}</p> : null}
        </Card>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <div id="preview">
            <Card>
              <h2 className="font-black">{t("admin.puzzlePreview")}</h2>
              {puzzle.fen ? (
                <div dir="ltr" className="mx-auto mt-2 max-w-sm">
                  <ChessBoard pieces={fenToPieces(puzzle.fen)} disabled />
                </div>
              ) : (
                <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
              )}
              <p className="mt-2 break-all font-mono text-xs text-stone-500" dir="ltr">{puzzle.fen ?? "—"}</p>
            </Card>
          </div>
          <Card>
            <h2 className="font-black">{t("admin.expectedAnswer")}</h2>
            {contract ? (
              <>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.answerType")}: <b dir="ltr">{contract.answer_type}</b> ·{" "}
                  {t("admin.answerAttemptField")}: <b dir="ltr">{contract.attempt_field}</b>
                </p>
                <div className="mt-2 rounded-2xl bg-stone-50 p-3">
                  <AnswerEditor
                    contract={contract}
                    answer={puzzle.answer_json}
                    onChange={() => undefined}
                    disabled
                  />
                </div>
              </>
            ) : (
              <p className="mt-2 break-all font-mono text-xs" dir="ltr">{answerSummary(puzzle.answer_json)}</p>
            )}
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <Card>
            <h2 className="font-black">{t("admin.difficulty")} · {t("admin.rating")}</h2>
            <div className="mt-2 grid grid-cols-5 gap-1" dir="ltr">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  type="button"
                  disabled={busy || metadataLocked}
                  onClick={() => setDifficulty((current) => current === String(level) ? "" : String(level))}
                  className={`min-h-[44px] rounded-xl border font-black ${
                    difficulty === String(level)
                      ? "border-violet-700 bg-violet-700 text-white"
                      : "border-stone-200 bg-white"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
            <label className="mt-3 block text-sm font-bold" htmlFor="detail-rating">{t("admin.rating")}</label>
            <input
              id="detail-rating"
              dir="ltr"
              inputMode="decimal"
              value={rating}
              disabled={busy || metadataLocked}
              onChange={(event) => setRating(event.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm"
            />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-xl bg-stone-50 p-2 text-sm">
                <p className="text-xs text-stone-500">{t("admin.editor.targetRating")}</p>
                <p className="font-mono" dir="ltr">{puzzle.target_rating ?? "—"}</p>
              </div>
              <div className="rounded-xl bg-stone-50 p-2 text-sm">
                <p className="text-xs text-stone-500">{t("admin.label.difficulty")}</p>
                <p className="font-mono" dir="ltr">{puzzle.difficulty ?? "—"}</p>
              </div>
            </div>
            <Button disabled={busy || metadataLocked} onClick={() => void onSaveMeta()} className="mt-3 w-full">
              {t("profile.save")}
            </Button>
          </Card>

          <Card>
            <h2 className="font-black">{t("admin.validationState")}</h2>
            {lastValidation ? (
              <div className="mt-1 text-sm">
                <p className="font-bold">{validationLabel(lastValidation.status)}</p>
                <p className="text-xs text-stone-500" dir="ltr">
                  {lastValidation.validator_version} · {formatDate(lastValidation.created_at)}
                </p>
              </div>
            ) : (
              <p className="mt-1 text-sm text-stone-500">{t("admin.neverValidated")}</p>
            )}
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {["draft", "validated"].includes(puzzle.status) ? (
                <Button disabled={busy} onClick={() => void act(() => adminApi.validatePuzzle(puzzle.id))}>
                  {t("admin.validate")}
                </Button>
              ) : null}
              <Button disabled={busy} variant="secondary" onClick={() => void onPreview()}>
                {t("admin.validateBeforeSave")}
              </Button>
            </div>
            {preview ? (
              <div className={`mt-2 text-sm font-bold ${preview.ok ? "text-emerald-700" : "text-red-600"}`}>
                <p>{preview.ok ? t("admin.validationPassed") : t("admin.validationFailed")}</p>
                 {preview.errors.length > 0 ? (
                   <p className="mt-1 text-xs">
                     {t("admin.editor.validationErrorsCount").replace("{count}", faNum(preview.errors.length))}
                   </p>
                 ) : null}
              </div>
            ) : null}
          </Card>
        </div>

        <Card>
          <h2 className="font-black">{t("admin.lifecycleState")}</h2>
          {meaningLocked && puzzle.status !== "published" ? (
            <p className="mt-1 text-xs text-stone-500">{t("admin.deleteBlocked")}</p>
          ) : null}
          <label className="mt-2 block text-sm font-bold" htmlFor="detail-reason">{t("admin.label.reason")}</label>
          <input
            id="detail-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("admin.label.reason")}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {puzzle.status === "draft" ? (
              <>
                <Button disabled={busy} onClick={() => void act(() => adminApi.validatePuzzle(puzzle.id))}>{t("admin.validate")}</Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.rejectConfirm"), () => void act(() => adminApi.rejectPuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.reject")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "validated" ? (
              <>
                <Button disabled={busy} onClick={() => void act(() => adminApi.reviewPuzzle(puzzle.id, { decision: "approve", notes: reason }))}>
                  {t("admin.reviewApprove")}
                </Button>
                <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act(() => adminApi.reviewPuzzle(puzzle.id, { decision: "request_changes", notes: reason }))}>
                  {t("admin.reviewRequestChanges")}
                </Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.quarantineConfirm"), () => void act(() => adminApi.quarantinePuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.quarantine")}
                </Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.rejectConfirm"), () => void act(() => adminApi.rejectPuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.reject")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "reviewed" ? (
              <>
                <Button disabled={busy} onClick={() => void act(() => adminApi.approvePuzzle(puzzle.id))}>{t("admin.approve")}</Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.quarantineConfirm"), () => void act(() => adminApi.quarantinePuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.quarantine")}
                </Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.rejectConfirm"), () => void act(() => adminApi.rejectPuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.reject")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "approved" ? (
              <>
                <Button disabled={busy} onClick={() => void act(() => adminApi.publishPuzzle(puzzle.id))}>{t("admin.publish")}</Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.quarantineConfirm"), () => void act(() => adminApi.quarantinePuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.quarantine")}
                </Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.rejectConfirm"), () => void act(() => adminApi.rejectPuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.reject")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "published" ? (
              <>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.quarantineConfirm"), () => void act(() => adminApi.quarantinePuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.quarantine")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "quarantined" ? (
              <>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.releaseConfirm"), () => void act(() => adminApi.releasePuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.release")}
                </Button>
                <Button
                  disabled={busy || !reason.trim()}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.rejectConfirm"), () => void act(() => adminApi.rejectPuzzle(puzzle.id, reason.trim())))}
                >
                  {t("admin.reject")}
                </Button>
                <Button
                  disabled={busy}
                  variant="secondary"
                  onClick={() => confirmLifecycle(t("admin.retireConfirm"), () => void act(() => adminApi.retirePuzzle(puzzle.id)))}
                >
                  {t("admin.retire")}
                </Button>
              </>
            ) : null}
            {puzzle.status === "retired" || puzzle.status === "archived" ? (
              <Button
                disabled={busy}
                variant="secondary"
                onClick={() => confirmLifecycle(t("admin.restoreConfirm"), () => void act(() => adminApi.restorePuzzle(puzzle.id, reason.trim())))}
              >
                {t("admin.restore")}
              </Button>
            ) : null}
            {puzzle.status === "rejected" ? <p className="text-sm text-stone-500">{t("admin.deleteBlocked")}</p> : null}
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <Card>
            <h2 className="font-black">{t("admin.label.usage")}</h2>
            {usage ? (
              <div className="mt-2 text-sm">
                <p>{t("admin.attempts")}: <b>{faNum(usage.attempts)}</b></p>
                <p>{t("admin.successRate")}: <b>{usage.success_rate === null ? "—" : faPercent(usage.success_rate)}</b></p>
                <p>{t("admin.avgDuration")}: <b>{usage.avg_duration_ms === null ? "—" : faNum(Math.round(usage.avg_duration_ms / 1000))}</b></p>
                <p className="mt-2 text-xs text-stone-500" dir="ltr">
                   {Object.entries(usage.by_result).map(([result, count]) => `${resultLabel(result)}=${faNum(count)}`).join(" · ") || "—"}
                </p>
              </div>
            ) : (
              <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
            )}
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.label.source")}</h2>
            <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-stone-500">{t("admin.source")}</dt>
                <dd>{sourceLabel(puzzle.source)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.editor.sourceReference")}</dt>
                <dd className="break-all" dir="ltr">{puzzle.source_reference || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.runDetail")}</dt>
                <dd dir="ltr">{puzzle.generator_run_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.label.created")}</dt>
                <dd dir="ltr">{formatDate(puzzle.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.label.updated")}</dt>
                <dd>{t("admin.updatedUnavailable")}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.statusPublished")}</dt>
                <dd dir="ltr">{puzzle.published_at ? formatDate(puzzle.published_at) : "—"}</dd>
              </div>
            </dl>
          </Card>
        </div>

        <Card>
          <h2 className="font-black">{t("admin.history")}</h2>
          {timeline.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ol className="mt-2 flex flex-col gap-2">
              {timeline.map((event) => (
                <li key={event.id} className="rounded-2xl bg-stone-50 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold">{event.title}</p>
                    <time className="text-xs text-stone-500" dir="ltr">{formatDate(event.at)}</time>
                  </div>
                  <p className="mt-1 text-xs text-stone-500">
                    {t("admin.label.user")}: <span dir="ltr">{event.actor ?? "—"}</span>
                  </p>
                  {event.reason ? <p className="mt-1 text-xs text-stone-600">{event.reason}</p> : null}
                   {event.technical ? <p className="mt-1 text-[11px] text-stone-400">{t("admin.details")}</p> : null}
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </>
  );
}
