import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AdminPuzzle } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

function statusLabel(status: string): string {
  if (status === "published") return t("admin.statusPublished");
  if (status === "archived") return t("admin.statusArchived");
  return t("admin.statusDraft");
}

// Puzzle lifecycle foundation: drafts, publish, retire. Published
// content is immutable in meaning; retirement preserves history.
// Full validate/review/approve belongs to the later content phase.
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

  async function onPublish(id: number) {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.publishPuzzle(id);
      load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onRetire(id: number) {
    if (!window.confirm(t("admin.retireConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.retirePuzzle(id);
      load();
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
    setBusy(true);
    setNotice("");
    try {
      await adminApi.createPuzzle({
        exercise_slug: newSlug.trim(),
        prompt_fa: newPrompt,
        answer_json: {},
      });
      setNewSlug("");
      setNewPrompt("");
      load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.puzzles")} subtitle={t("admin.subtitle")} />
      <Card>
        <div className="grid grid-cols-2 gap-2">
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
            <option value="published">{t("admin.statusPublished")}</option>
            <option value="archived">{t("admin.statusArchived")}</option>
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
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {p.status === "draft" ? (
                    <Button disabled={busy} onClick={() => void onPublish(p.id)}>
                      {t("admin.publish")}
                    </Button>
                  ) : (
                    <span />
                  )}
                  {p.status !== "archived" ? (
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void onRetire(p.id)}
                    >
                      {t("admin.retire")}
                    </Button>
                  ) : (
                    <span />
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
