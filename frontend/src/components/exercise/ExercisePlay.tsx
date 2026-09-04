import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

function OptionResultRow({
  item,
  result,
}: {
  item: PlayOptionItem;
  result: AttemptResponse;
}) {
  const state = result.detail.correct.includes(item.id)
    ? "correct"
    : result.detail.missed.includes(item.id)
      ? "missed"
      : result.detail.wrong.includes(item.id)
        ? "wrong"
        : "idle";
  const styles: Record<string, string> = {
    correct: "border-green-500 bg-green-50 text-green-800",
    missed: "border-amber-500 bg-amber-50 text-amber-800",
    wrong: "border-red-400 bg-red-50 text-red-700",
    idle: "border-stone-200 bg-white text-stone-500",
  };
  return (
    <div
      className={`flex min-h-[44px] items-center justify-between rounded-2xl border-2 px-4 py-3 text-base font-bold ${styles[state]}`}
    >
      <span>{t(item.labelKey)}</span>
      <span aria-hidden="true">{state === "correct" ? "✓" : state === "missed" ? "!" : state === "wrong" ? "✕" : "·"}</span>
    </div>
  );
}

export interface PlayOptionItem {
  id: string;
  labelKey: FaKey;
  groupKey: FaKey;
}

export interface ExercisePlayConfig {
  slug: string;
  titleKey: FaKey;
  introKey: FaKey;
  /** Task square to highlight (e.g. the target piece). Null when none. */
  targetOf: (puzzle: Puzzle) => string | null;
  /** Build the attempt answer payload from selected IDs.
   * Default sends board squares; option exercises send their own shape. */
  answerOf?: (selected: string[]) => Record<string, unknown>;
  /** Fixed option list (e.g. castling choices). When present, selection
   * happens on these controls instead of board squares. */
  options?: PlayOptionItem[];
  /** Map a detail ID (square or option) to display text. Default: identity. */
  detailLabelOf?: (id: string) => string;
}

// Shared Entry → Play → Feedback/Education → Next loop for square-selection
// exercises. Renders and transports answers only; the backend decides
// correctness, scoring, and rating.
export function ExercisePlay({ config }: { config: ExercisePlayConfig }) {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader title={t(config.titleKey)} subtitle={t(config.introKey)} />
        <Card>
          <p className="mb-1 text-sm text-stone-500">{t("play.mode")}</p>
          <div className="flex gap-2">
            <Button
              variant={mode === "practice" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("practice")}
            >
              {t("play.practice")}
            </Button>
            <Button
              variant={mode === "rated" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("rated")}
            >
              {t("play.rated")}
            </Button>
          </div>
          <Button className="mt-4 w-full" onClick={() => setStarted(true)}>
            {t("play.start")}
          </Button>
        </Card>
      </div>
    );
  }

  return <PlayLoop config={config} mode={mode} onChangeMode={setMode} />;
}

function PlayLoop({
  config,
  mode,
  onChangeMode,
}: {
  config: ExercisePlayConfig;
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles(config.slug));
    } catch {
      setError(t("common.error"));
    }
  }, [config.slug]);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const pieces = useMemo(() => fenToPieces(puzzle?.fen ?? null), [puzzle]);
  const target = puzzle ? config.targetOf(puzzle) : null;

  function resetForPuzzle() {
    setSelected([]);
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
    resetForPuzzle();
  }

  function toggleSquare(square: string) {
    if (result) return; // Locked after submission; feedback shows states.
    toggleSelected(square);
  }

  function toggleSelected(id: string) {
    if (result) return; // Locked after submission; feedback shows states.
    setSelected((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  }

  async function submit(clientResult?: string) {
    if (!puzzle || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: config.answerOf ? config.answerOf(selected) : { selected_squares: selected },
        mode,
        hints_used: usedHints,
        started_at: startedAt,
        client_result: clientResult ?? null,
      });
      setResult(res);
    } catch {
      setError(mode === "rated" ? t("play.authRequired") : t("common.error"));
    } finally {
      setSubmitting(false);
    }
  }

  if (error && puzzles === null) {
    return (
      <Card>
        <p>{error}</p>
        <Button className="mt-3" onClick={load}>
          {t("common.retry")}
        </Button>
      </Card>
    );
  }
  if (puzzles === null) return <p>{t("common.loading")}</p>;
  if (puzzles.length === 0 || !puzzle) {
    return (
      <Card>
        <Badge>{t("exercise.comingSoon")}</Badge>
        <p className="mt-2">{t("exercises.empty")}</p>
      </Card>
    );
  }

  const hints = puzzle.hint_json.hints ?? [];
  const labelOf = config.detailLabelOf ?? ((id: string) => id);
  const useOptions = config.options !== undefined;
  const optionGroups: { key: FaKey; items: PlayOptionItem[] }[] = [];
  for (const item of config.options ?? []) {
    const group = optionGroups.find((g) => g.key === item.groupKey);
    if (group) group.items.push(item);
    else optionGroups.push({ key: item.groupKey, items: [item] });
  }
  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">> = {};
  if (target) squareStates[target] = "target";
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  } else if (!useOptions) {
    for (const s of selected) squareStates[s] = "selected";
  }

  return (
    <div>
      <PageHeader title={t(config.titleKey)} subtitle={puzzle.prompt_fa} />
      <div className="mb-3 flex items-center gap-2">
        <Badge>
          {faNum(index + 1)} / {faNum(puzzles.length)}
        </Badge>
        <button
          className="min-h-[44px] rounded-full bg-violet-100 px-4 text-sm font-bold text-violet-700"
          onClick={() => onChangeMode(mode === "practice" ? "rated" : "practice")}
        >
          {mode === "practice" ? t("play.practice") : t("play.rated")}
        </button>
      </div>

      <ChessBoard
        pieces={pieces}
        onSquarePress={useOptions ? undefined : toggleSquare}
        squareStates={squareStates}
        disabled={result !== null || submitting}
      />

      {!result ? (
        <div>
          {useOptions ? (
            <div className="mt-3 grid gap-3">
              {optionGroups.map((group) => (
                <Card key={group.key}>
                  <p className="text-base font-black text-stone-800">{t(group.key)}</p>
                  <div className="mt-2 grid gap-2">
                    {group.items.map((item) => {
                      const active = selected.includes(item.id);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          aria-pressed={active}
                          disabled={submitting}
                          onClick={() => toggleSelected(item.id)}
                          className={`flex min-h-[44px] items-center justify-between rounded-2xl border-2 px-4 py-3 text-base font-bold transition ${
                            active
                              ? "border-violet-600 bg-violet-50 text-violet-800"
                              : "border-stone-200 bg-white text-stone-700"
                          }`}
                          style={{ touchAction: "manipulation" }}
                        >
                          <span>{t(item.labelKey)}</span>
                          <span
                            aria-hidden="true"
                            className={`flex h-6 w-6 items-center justify-center rounded-md border-2 ${
                              active ? "border-violet-600 bg-violet-600 text-white" : "border-stone-300 text-transparent"
                            }`}
                          >
                            ✓
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </Card>
              ))}
            </div>
          ) : null}
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("play.selected")}: {faNum(selected.length)}
          </p>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setSelected([])} disabled={submitting}>
              {t("play.clear")}
            </Button>
          </div>
          {hints.length > 0 ? (
            <Card className="mt-3">
              <p className="text-sm font-black">{t("play.hints")}</p>
              {hints.map((h) => {
                const revealed = usedHints.includes(h.id);
                return (
                  <div key={h.id} className="mt-2 flex items-center justify-between gap-2">
                    {revealed ? (
                      <p className="text-sm">{h.text_fa}</p>
                    ) : (
                      <Button variant="ghost" className="px-2" onClick={() => setUsedHints((p) => [...p, h.id])}>
                        {t("play.useHint")}
                      </Button>
                    )}
                    {revealed ? <Badge>{t("play.hintUsed")}</Badge> : null}
                  </div>
                );
              })}
            </Card>
          ) : null}
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        <Card className="mt-3">
          <div className="flex gap-4 text-center">
            <div className="flex-1">
              <p className="text-2xl font-black text-green-600">{faNum(result.detail.correct.length)}</p>
              <p className="text-xs text-stone-500">{t("play.correctCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-amber-600">{faNum(result.detail.missed.length)}</p>
              <p className="text-xs text-stone-500">{t("play.missedCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-red-600">{faNum(result.detail.wrong.length)}</p>
              <p className="text-xs text-stone-500">{t("play.wrongCount")}</p>
            </div>
          </div>
          {useOptions ? (
            <div className="mt-3 grid gap-3">
              {optionGroups.map((group) => (
                <div key={group.key}>
                  <p className="text-sm font-black text-stone-800">{t(group.key)}</p>
                  <div className="mt-1 grid gap-2">
                    {group.items.map((item) => (
                      <OptionResultRow key={item.id} item={item} result={result} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          <p className="mt-3 text-sm font-bold">
            {t("play.correctAnswer")}:{" "}
            {result.detail.correct.concat(result.detail.missed).map(labelOf).join("، ")}
          </p>
          {puzzle.explanation ? (
            <p className="mt-2 text-sm text-stone-600">
              {t("play.explanation")}: {puzzle.explanation}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <Button className="flex-1" onClick={goNext}>
              {t("play.next")}
            </Button>
            <Button variant="secondary" onClick={resetForPuzzle}>
              {t("play.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
