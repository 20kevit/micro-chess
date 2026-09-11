import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { Generator, GeneratorRun } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Generator administration: registry inspection, bounded generation
// jobs, and run history. Generated content stays non-production until
// it passes the normal review/approval gates; the server owns every
// check and this UI only reflects server state.
export function AdminGeneratorsPage() {
  const [generators, setGenerators] = useState<Generator[]>([]);
  const [runs, setRuns] = useState<GeneratorRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [code, setCode] = useState("");
  const [count, setCount] = useState("5");
  const [seed, setSeed] = useState("");
  const [targetRating, setTargetRating] = useState("");
  const [difficulty, setDifficulty] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    Promise.all([adminApi.generators(), adminApi.generatorRuns({ page_size: 20 })])
      .then(([registry, history]) => {
        setGenerators(registry);
        setRuns(history);
        if (!code && registry.length > 0) setCode(registry[0]?.code ?? "");
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [code]);

  useEffect(() => {
    load();
  }, [load]);

  async function onRun() {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.runGenerator(code, {
        count: Math.max(1, Math.min(50, Number(count) || 1)),
        seed: seed.trim() === "" ? undefined : Number(seed),
        target_rating: targetRating.trim() === "" ? undefined : Number(targetRating),
        difficulty: difficulty.trim() === "" ? undefined : Number(difficulty),
        config: {},
      });
      setSeed("");
      load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onCancel(id: number) {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.cancelGeneratorRun(id);
      load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.generators")} subtitle={t("admin.subtitle")} />
      <Card>
        <div className="flex flex-col gap-2">
          <select
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
            dir="ltr"
          >
            {generators.map((g) => (
              <option key={g.code} value={g.code}>
                {g.code} · v{g.version}
              </option>
            ))}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <input
              value={count}
              onChange={(e) => setCount(e.target.value)}
              placeholder={t("admin.count")}
              inputMode="numeric"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
              dir="ltr"
            />
            <input
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder={t("admin.seed")}
              inputMode="numeric"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
              dir="ltr"
            />
            <input
              value={targetRating}
              onChange={(e) => setTargetRating(e.target.value)}
              placeholder={t("admin.targetRating")}
              inputMode="decimal"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
              dir="ltr"
            />
            <input
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              placeholder={`${t("admin.difficulty")} (1-5)`}
              inputMode="numeric"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
              dir="ltr"
            />
          </div>
          <Button disabled={busy || !code} onClick={() => void onRun()}>
            {t("admin.runGenerator")}
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
      ) : (
        <>
          <h2 className="mt-4 font-black">{t("admin.generatorRuns")}</h2>
          {runs.length === 0 ? (
            <Card>
              <p className="text-center text-stone-500">{t("admin.empty")}</p>
            </Card>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {runs.map((run) => (
                <li key={run.id}>
                  <Card>
                    <div className="flex min-h-[44px] items-center justify-between gap-2">
                      <span className="font-bold" dir="ltr">
                        #{run.id} · {run.generator_code}
                      </span>
                      <Badge>{run.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-stone-500" dir="ltr">
                      accepted {run.accepted_count} · rejected {run.rejected_count}
                      {run.seed !== null ? ` · seed ${run.seed}` : null} · v{run.generator_version}
                    </p>
                    {(run.result.accepted_puzzle_ids ?? []).length > 0 ? (
                      <p className="mt-1 text-xs text-stone-500" dir="ltr">
                        {t("admin.accepted")}: {(run.result.accepted_puzzle_ids ?? []).join(", ")}
                      </p>
                    ) : null}
                    {run.error ? <p className="mt-1 text-xs font-bold text-red-600" dir="ltr">{run.error}</p> : null}
                    {(run.status === "queued" || run.status === "running") && (
                      <div className="mt-2">
                        <Button variant="secondary" disabled={busy} onClick={() => void onCancel(run.id)}>
                          {t("admin.cancel")}
                        </Button>
                      </div>
                    )}
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
