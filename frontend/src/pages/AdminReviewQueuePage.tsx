import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminExercise, AnswerContract, ReviewQueueItem } from "../api/types";
import type { FaKey } from "../i18n/fa";
import { ChessBoard } from "../components/chess/ChessBoard";
import { AnswerEditor, answerSummary } from "../components/content/AnswerEditor";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";
import { faNum, faPercent } from "../lib/playerDisplay";

const PAGE_SIZE = 20;
const STATUSES = ["draft", "validated", "reviewed", "approved", "published", "quarantined", "rejected", "retired"];
const REASON_KEYS: Record<string, FaKey> = {
  awaiting_review: "admin.review.reason.awaitingReview",
  high_failure_rate: "admin.review.reason.highFailure",
  quarantined: "admin.review.reason.quarantined",
  low_usage: "admin.review.reason.lowUsage",
  stale: "admin.review.reason.stale",
  validation_failed: "admin.review.reason.validationFailed",
  insufficient_data: "admin.review.reason.insufficientData",
  awaiting_publish: "admin.review.reason.awaitingPublish",
};
const MEANING_LOCKED = new Set(["published", "retired", "archived", "rejected", "quarantined"]);
type QueueAction =
  | "validate"
  | "review_approve"
  | "request_changes"
  | "approve"
  | "publish"
  | "quarantine"
  | "reject"
  | "retire"
  | "release"
  | "restore";

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

function validationStatusLabel(status: string): string {
  if (status === "pass") return t("admin.validationPassed");
  if (status === "fail") return t("admin.validationFailed");
  return t("admin.unknown");
}

function reasonLabel(reason: string): string {
  const key = REASON_KEYS[reason];
  return key ? t(key) : t("admin.review.reason.other");
}

function severityLabel(severity: string): string {
  if (severity === "high") return t("admin.status.high");
  if (severity === "medium") return t("admin.status.medium");
  if (severity === "normal") return t("admin.status.normal");
  return t("admin.unknown");
}

function exerciseLabel(exercises: AdminExercise[], slug: string): string {
  return exercises.find((item) => item.slug === slug)?.title_fa ?? slug;
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

export function AdminReviewQueuePage() {
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [exercises, setExercises] = useState<AdminExercise[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [exercise, setExercise] = useState(searchParams.get("exercise") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [contract, setContract] = useState<AnswerContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (typeof adminApi.exercises !== "function") return;
    Promise.resolve(adminApi.exercises()).then((rows) => setExercises(rows ?? [])).catch(() => setExercises([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const loader = typeof adminApi.reviewQueuePage === "function"
        ? adminApi.reviewQueuePage
        : adminApi.reviewQueue;
      const response = await loader({
        exercise: exercise || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      if (Array.isArray(response)) {
        setItems(response);
        setTotal(response.length);
      } else {
        setItems(response.items);
        setTotal(response.total);
      }
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [exercise, page, status]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
  }, [items]);

  const selected = items.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    if (!selected || typeof adminApi.answerContract !== "function") {
      setContract(null);
      return;
    }
    let active = true;
    setContract(null);
    adminApi.answerContract(selected.exercise_slug)
      .then((next) => {
        if (active) setContract(next);
      })
      .catch(() => {
        if (active) setContract(null);
      });
    return () => {
      active = false;
    };
  }, [selected?.exercise_slug, selected?.id]);

  function resetContext() {
    setPage(1);
    setSelectedId(null);
    setNotice("");
  }

  async function act(action: QueueAction) {
    if (!selected || busy) return;
    const cleanReason = reason.trim();
    if (["quarantine", "reject", "request_changes", "release", "restore"].includes(action) && !cleanReason) return;
    let confirmed = true;
    if (action === "quarantine") confirmed = window.confirm(t("admin.quarantineConfirm"));
    if (action === "reject") confirmed = window.confirm(t("admin.rejectConfirm"));
    if (action === "retire") confirmed = window.confirm(t("admin.retireConfirm"));
    if (action === "publish") confirmed = window.confirm(t("admin.bulkConfirm"));
    if (action === "release") confirmed = window.confirm(t("admin.releaseConfirm"));
    if (action === "restore") confirmed = window.confirm(t("admin.restoreConfirm"));
    if (!confirmed) return;
    setBusy(true);
    setNotice("");
    try {
      if (action === "validate") await adminApi.validatePuzzle(selected.id);
      if (action === "review_approve") await adminApi.reviewPuzzle(selected.id, { decision: "approve", notes: cleanReason });
      if (action === "request_changes") await adminApi.reviewPuzzle(selected.id, { decision: "request_changes", notes: cleanReason });
      if (action === "approve") await adminApi.approvePuzzle(selected.id);
      if (action === "publish") await adminApi.publishPuzzle(selected.id);
      if (action === "quarantine") await adminApi.quarantinePuzzle(selected.id, cleanReason);
      if (action === "reject") await adminApi.rejectPuzzle(selected.id, cleanReason);
      if (action === "retire") await adminApi.retirePuzzle(selected.id);
      if (action === "release") await adminApi.releasePuzzle(selected.id, cleanReason);
      if (action === "restore") await adminApi.restorePuzzle(selected.id, cleanReason);
      setReason("");
      await load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  const reasonRequired = selected?.status === "validated"
    || selected?.status === "reviewed"
    || selected?.status === "approved"
    || selected?.status === "published"
    || selected?.status === "quarantined"
    || selected?.status === "draft";

  return (
    <>
      <PageHeader title={t("admin.reviewQueue")} subtitle={t("admin.reviewSubtitle")} />
      <Card>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <label className="text-sm font-bold" htmlFor="review-exercise">
            {t("admin.label.exercise")}
            <select
              id="review-exercise"
              value={exercise}
              onChange={(event) => {
                setExercise(event.target.value);
                resetContext();
              }}
              className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal"
            >
              <option value="">{t("admin.all")}</option>
              {exercises.map((item) => <option key={item.slug} value={item.slug}>{item.title_fa} · {item.slug}</option>)}
            </select>
          </label>
          <label className="text-sm font-bold" htmlFor="review-status">
            {t("admin.label.status")}
            <select
              id="review-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                resetContext();
              }}
              className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal"
            >
              <option value="">{t("admin.allStatuses")}</option>
              {STATUSES.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <span className="min-h-[44px] text-sm text-stone-500">{t("admin.table.total")}: {faNum(total)}</span>
          </div>
        </div>
        <p className="mt-2 text-xs text-stone-500">{t("admin.review.workspace")}</p>
      </Card>

      {notice ? <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={() => void load()} className="mx-auto mt-3 max-w-xs">{t("common.retry")}</Button>
        </div>
      ) : items.length === 0 ? (
        <Card><p className="text-center text-stone-500">{t("admin.empty")}</p></Card>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="xl:sticky xl:top-4 xl:self-start">
            <h2 className="font-black">{t("admin.reviewQueue")}</h2>
            <ul className="mt-2 flex max-h-[720px] flex-col gap-2 overflow-y-auto pl-1">
              {items.map((item) => {
                const active = item.id === selectedId;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      aria-pressed={active}
                      className={`min-h-[72px] w-full rounded-2xl border p-3 text-right ${
                        active ? "border-violet-700 bg-violet-50" : "border-stone-200 bg-white"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <b dir="ltr">#{item.id} · {exerciseLabel(exercises, item.exercise_slug)}</b>
                        <Badge>{statusLabel(item.status)}</Badge>
                      </span>
                      <span className="mt-2 flex items-center justify-between text-xs text-stone-500">
                        <span>{severityLabel(item.severity)}</span>
                        <span>{t("admin.label.usage")}: {faNum(item.usage_attempts ?? item.attempts ?? 0)}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>

          {selected ? (
            <div className="flex flex-col gap-2">
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-black" dir="ltr">#{selected.id} · {exerciseLabel(exercises, selected.exercise_slug)}</p>
                    <p className="mt-1 text-sm">{selected.prompt_fa || t("admin.empty")}</p>
                  </div>
                  <Badge>{statusLabel(selected.status)}</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-sm font-bold text-violet-700">
                  <Link to={`/admin/puzzles/${selected.id}`} className="inline-flex min-h-[44px] items-center">
                    {t("admin.reviewQueueOpen")}
                  </Link>
                  {!MEANING_LOCKED.has(selected.status) ? (
                    <Link to={`/admin/puzzles/${selected.id}/edit`} className="inline-flex min-h-[44px] items-center">
                      {t("admin.editPuzzle")}
                    </Link>
                  ) : null}
                  <Link to={`/admin/puzzles/${selected.id}#preview`} className="inline-flex min-h-[44px] items-center">
                    {t("admin.review.preview")}
                  </Link>
                </div>
              </Card>

              <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                <Card>
                  <h2 className="font-black">{t("admin.review.preview")}</h2>
                  {selected.fen ? (
                    <div dir="ltr" className="mx-auto mt-2 max-w-sm">
                      <ChessBoard pieces={fenToPieces(selected.fen)} disabled />
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
                  )}
                  <p className="mt-2 break-all font-mono text-xs text-stone-500" dir="ltr">{selected.fen ?? "—"}</p>
                </Card>
                <Card>
                  <h2 className="font-black">{t("admin.review.answer")}</h2>
                  {contract ? (
                    <div className="mt-2 rounded-2xl bg-stone-50 p-3">
                      <AnswerEditor
                        contract={contract}
                        answer={selected.answer_json ?? {}}
                        onChange={() => undefined}
                        disabled
                      />
                    </div>
                  ) : (
                    <p className="mt-2 break-all font-mono text-xs" dir="ltr">{answerSummary(selected.answer_json ?? {})}</p>
                  )}
                </Card>
              </div>

              <Card>
                <h2 className="font-black">{t("admin.explanation")}</h2>
                <p className="mt-2 text-sm text-stone-600">{selected.explanation || t("admin.empty")}</p>
              </Card>

              <Card>
                <h2 className="font-black">{t("admin.details")}</h2>
                <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.source")}</dt>
                    <dd>{sourceLabel(selected.source)}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.editor.sourceReference")}</dt>
                    <dd className="break-all" dir="ltr">{selected.source_reference || "—"}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.runDetail")}</dt>
                    <dd dir="ltr">{selected.generator_run_id ?? "—"}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.review.creator")}</dt>
                    <dd dir="ltr">
                      {selected.creator?.display_name || selected.creator_display_name || selected.creator_username || selected.creator?.username || "—"}
                    </dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.review.validation")}</dt>
                    <dd>
                      {selected.latest_validation_status || selected.validation_status
                        ? validationStatusLabel(selected.latest_validation_status ?? selected.validation_status ?? "")
                        : t("admin.neverValidated")}
                    </dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.usage")}</dt>
                    <dd>{faNum(selected.usage_attempts ?? selected.attempts ?? 0)}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.failureRate")}</dt>
                    <dd>{selected.failure_rate === null || selected.failure_rate === undefined ? "—" : faPercent(selected.failure_rate)}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.difficulty")}</dt>
                    <dd dir="ltr">{selected.difficulty ?? "—"}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.label.rating")}</dt>
                    <dd dir="ltr">{faNum(selected.initial_rating)}</dd>
                  </div>
                  <div className="rounded-xl bg-stone-50 p-2">
                    <dt className="text-xs text-stone-500">{t("admin.review.created")}</dt>
                    <dd dir="ltr">{formatDate(selected.created_at)}</dd>
                  </div>
                </dl>
                {selected.reasons.length > 0 ? (
                  <ul className="mt-3 flex flex-wrap gap-1" dir="ltr">
                    {selected.reasons.map((item) => <li key={item} className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800">{reasonLabel(item)}</li>)}
                  </ul>
                ) : null}
              </Card>

              <Card>
                <h2 className="font-black">{t("admin.lifecycleState")}</h2>
                <label className="mt-2 block text-sm font-bold" htmlFor="review-reason">{t("admin.label.reason")}</label>
                <input
                  id="review-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder={t("admin.label.reason")}
                  className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
                />
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {selected.status === "draft" ? (
                    <>
                      <Button disabled={busy} onClick={() => void act("validate")}>{t("admin.validate")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("reject")}>{t("admin.reject")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "validated" ? (
                    <>
                      <Button disabled={busy} onClick={() => void act("review_approve")}>{t("admin.reviewApprove")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("request_changes")}>{t("admin.reviewRequestChanges")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("quarantine")}>{t("admin.quarantine")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("reject")}>{t("admin.reject")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "reviewed" ? (
                    <>
                      <Button disabled={busy} onClick={() => void act("approve")}>{t("admin.approve")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("quarantine")}>{t("admin.quarantine")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("reject")}>{t("admin.reject")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "approved" ? (
                    <>
                      <Button disabled={busy} onClick={() => void act("publish")}>{t("admin.publish")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("quarantine")}>{t("admin.quarantine")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("reject")}>{t("admin.reject")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "published" ? (
                    <>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("quarantine")}>{t("admin.quarantine")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "quarantined" ? (
                    <>
                      <Button disabled={busy} onClick={() => void act("release")}>{t("admin.release")}</Button>
                      <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void act("reject")}>{t("admin.reject")}</Button>
                      <Button disabled={busy} variant="secondary" onClick={() => void act("retire")}>{t("admin.retire")}</Button>
                    </>
                  ) : null}
                  {selected.status === "retired" || selected.status === "archived" ? (
                    <Button disabled={busy} onClick={() => void act("restore")}>{t("admin.restore")}</Button>
                  ) : null}
                  {selected.status === "rejected" ? <p className="text-sm text-stone-500">{t("admin.deleteBlocked")}</p> : null}
                </div>
                {reasonRequired ? <p className="mt-2 text-xs text-stone-500">{t("admin.label.reason")}</p> : null}
              </Card>
            </div>
          ) : (
            <Card><p className="text-stone-500">{t("admin.review.noSelection")}</p></Card>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
          {t("admin.pagination.previous")}
        </Button>
        <span className="text-center text-sm font-bold">
          {t("admin.pagination.summary")
            .replace("{page}", faNum(page))
            .replace("{pages}", faNum(pages))
            .replace("{total}", faNum(total))}
        </span>
        <Button variant="secondary" disabled={page >= pages} onClick={() => setPage((current) => Math.min(pages, current + 1))}>
          {t("admin.pagination.next")}
        </Button>
      </div>
    </>
  );
}
