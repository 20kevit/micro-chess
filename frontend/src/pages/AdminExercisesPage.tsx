import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AdminExercise, AdminExerciseDetail } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

// Exercise availability management: inspect, rename metadata, and
// enable/disable. Slugs are immutable; history is never rewritten.
export function AdminExercisesPage() {
  const [rows, setRows] = useState<AdminExercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<AdminExerciseDetail | null>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setFailed(false);
    try {
      setRows(await adminApi.exercises());
      setLoading(false);
    } catch {
      setFailed(true);
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function openDetail(slug: string) {
    setBusy(true);
    setNotice("");
    try {
      const detail = await adminApi.exercise(slug);
      setSelected(detail);
      setTitle(detail.title_fa);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function refresh(slug: string) {
    try {
      const detail = await adminApi.exercise(slug);
      setSelected(detail);
      setTitle(detail.title_fa);
    } catch {
      setNotice(t("common.error"));
    }
    await load();
  }

  async function onToggle(slug: string, next: boolean) {
    if (!next && !window.confirm(t("admin.disableConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.updateExercise(slug, { is_active: next });
      await refresh(slug);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveTitle(slug: string) {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.updateExercise(slug, { title_fa: title });
      await refresh(slug);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.exercises")} subtitle={t("admin.subtitle")} />
      {notice ? (
        <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p>
      ) : null}
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={() => void load()} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <p className="text-center text-stone-500">{t("admin.empty")}</p>
        </Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((e) => (
            <li key={e.slug}>
              <Card>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void openDetail(e.slug)}
                  className="flex min-h-[44px] w-full items-center justify-between gap-2 text-right"
                >
                  <span className="font-bold">{e.title_fa}</span>
                  <Badge>{e.is_active ? t("admin.statusEnabled") : t("admin.statusDisabled")}</Badge>
                </button>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {selected ? (
        <Card className="mt-3">
          <h2 className="font-black">{selected.title_fa}</h2>
          <p className="mt-1 text-xs text-stone-500" dir="ltr">
            {selected.slug} · {t("admin.puzzleCount")}: {faNum(selected.puzzle_count)} ·{" "}
            {t("admin.attempts")}: {faNum(selected.attempts_count)}
          </p>
          <label className="mt-3 block text-sm font-bold">{selected.title_fa}</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Button disabled={busy} onClick={() => void onSaveTitle(selected.slug)}>
              {t("profile.save")}
            </Button>
            {selected.is_active ? (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void onToggle(selected.slug, false)}
              >
                {t("admin.disable")}
              </Button>
            ) : (
              <Button disabled={busy} onClick={() => void onToggle(selected.slug, true)}>
                {t("admin.enable")}
              </Button>
            )}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
