import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AdminPuzzle, PuzzleHistory } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

function statusLabel(status: string): string {
  if (status === "validated") return t("admin.statusValidated");
  if (status === "reviewed") return t("admin.statusReviewed");
  if (status === "approved") return t("admin.statusApproved");
  if (status === "published") return t("admin.statusPublished");
  if (status === "retired" || status === "archived") return t("admin.statusRetired");
  return t("admin.statusDraft");
}

function sourceLabel(source: string): string {
  if (source === "generated") return t("admin.sourceGenerated");
  if (source === "imported") return t("admin.sourceImported");
  return t("admin.sourceManual");
}

// Puzzle lifecycle: draft → validated → reviewed → approved →
// published → retired. Every transition is server-enforced; the UI
// only reflects server state. Published answers stay immutable and
// retirement preserves history.
export function AdminPuzzlesPage() {
  const [rows, setRows] = useState<AdminPuzzle[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [exercise, setExercise] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [history, setHistory] = useState<Record<number, PuzzleHistory>>({});
  const [historyOpen, setHistoryOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    adminApi
      .puzzles({
        exercise: exercise || undefined,
        status: status || undefined,
        page_size: 50,
      })
      .then((list) => {
        setRows(list);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [exercise, status]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setNotice("");
    try {
      await fn();
      load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onHistory(id: number) {
    if (historyOpen === id) {
      setHistoryOpen(null);
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const detail = await adminApi.puzzleHistory(id);
      setHistory((prev) => ({ ...prev, [id]: detail }));
      setHistoryOpen(id);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onCreate() {
    if (!newSlug.trim()) {
      setNotice(t("common.error"));
      return;
    }
    await act(async () => {
      await adminApi.createPuzzle({
        exercise_slug: newSlug.trim(),
        prompt_fa: newPrompt,
        answer_json: {},
      });
      setNewSlug("");
      setNewPrompt("");
    });
  }

  return (
    <div>
      <PageHeader title={t("admin.puzzles")} subtitle={t("admin.subtitle")} />
      <Card>
        <p className="text-xs text-stone-500">{t("admin.lifecycleHint")}</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <input
            value={exercise}
            onChange={(e) => setExercise(e.target.value)}
            placeholder={t("progress.filterExercise")}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
            dir="ltr"
          />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
          >
            <option value="">{t("admin.allStatuses")}</option>
            <option value="draft">{t("admin.statusDraft")}</option>
            <option value="validated">{t("admin.statusValidated")}</option>
            <option value="reviewed">{t("admin.statusReviewed")}</option>
            <option value="approved">{t("admin.statusApproved")}</option>
            <option value="published">{t("admin.statusPublished")}</option>
            <option value="retired">{t("admin.statusRetired")}</option>
          </select>
        </div>
        <div className="mt-2 flex flex-col gap-2">
          <input
            value={newSlug}
            onChange={(e) => setNewSlug(e.target.value)}
            placeholder={t("progress.filterExercise")}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
            dir="ltr"
          />
          <input
            value={newPrompt}
            onChange={(e) => setNewPrompt(e.target.value)}
            placeholder={t("play.explanation")}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <Button disabled={busy} onClick={() => void onCreate()}>
            {t("admin.createDraft")}
          </Button>
        </div>
      </Card>
      {notice ? (
        <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p>
      ) : null}
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
        <Card>
          <p className="text-center text-stone-500">{t("admin.empty")}</p>
        </Card>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {rows.map((p) => (
            <li key={p.id}>
              <Card>
                <div className="flex min-h-[44px] items-center justify-between gap-2">
                  <span className="font-bold" dir="ltr">
                    #{p.id} · {p.exercise_slug}
                  </span>
                  <Badge>{statusLabel(p.status)}</Badge>
                </div>
                {p.prompt_fa ? <p className="mt-1 text-sm text-stone-500">{p.prompt_fa}</p> : null}
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.source")}: {sourceLabel(p.source)}
                  {p.difficulty ? ` · ${t("admin.difficulty")}: ${p.difficulty}` : null}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {p.status === "draft" ? (
                    <Button disabled={busy} onClick={() => void act(() => adminApi.validatePuzzle(p.id))}>
                      {t("admin.validate")}
                    </Button>
                  ) : (
                    <span />
                  )}
                  {p.status === "validated" ? (
                    <>
                      <Button
                        disabled={busy}
                        onClick={() => void act(() => adminApi.reviewPuzzle(p.id, { decision: "approve" }))}
                      >
                        {t("admin.reviewApprove")}
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() => void act(() => adminApi.reviewPuzzle(p.id, { decision: "request_changes" }))}
                      >
                        {t("admin.reviewRequestChanges")}
                      </Button>
                    </>
                  ) : null}
                  {p.status === "reviewed" ? (
                    <Button disabled={busy} onClick={() => void act(() => adminApi.approvePuzzle(p.id))}>
                      {t("admin.approve")}
                    </Button>
                  ) : (
                    <span />
                  )}
                  {p.status === "approved" ? (
                    <Button disabled={busy} onClick={() => void act(() => adminApi.publishPuzzle(p.id))}>
                      {t("admin.publish")}
                    </Button>
                  ) : (
                    <span />
                  )}
                  <Button variant="secondary" disabled={busy} onClick={() => void onHistory(p.id)}>
                    {t("admin.history")}
                  </Button>
                  {p.status !== "retired" && p.status !== "archived" ? (
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => {
                        if (!window.confirm(t("admin.retireConfirm"))) return;
                        void act(() => adminApi.retirePuzzle(p.id));
                      }}
                    >
                      {t("admin.retire")}
                    </Button>
                  ) : (
                    <span />
                  )}
                </div>
                {historyOpen === p.id && history[p.id] ? (
                  <div className="mt-2 rounded-xl bg-stone-50 p-3 text-xs" dir="ltr">
                    <p className="font-bold" dir="rtl">
                      {t("admin.history")}
                    </p>
                    <ul className="mt-1 flex flex-col gap-1">
                      {history[p.id].transitions.map((tr) => (
                        <li key={tr.id}>
                          {tr.from_status} → {tr.to_status}
                        </li>
                      ))}
                      {history[p.id].validations.map((v) => (
                        <li key={`v${v.id}`}>
                          validation: {v.status}
                          {(v.result.errors ?? []).map((e) => e.code).join(", ")
                            ? ` (${(v.result.errors ?? []).map((e) => e.code).join(", ")})`
                            : null}
                        </li>
                      ))}
                      {history[p.id].reviews.map((r) => (
                        <li key={`r${r.id}`}>review: {r.decision}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
