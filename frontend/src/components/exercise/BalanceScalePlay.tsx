import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { ChessPiece } from "../chess/ChessPiece";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

// Display-only piece values. The backend is authoritative for the verdict;
// this map only renders live totals while the child experiments.
const PIECE_VALUES: Record<string, number> = { P: 1, N: 3, B: 3, R: 5, Q: 9 };
const PIECE_ORDER = ["P", "N", "B", "R", "Q"];
const DRAG_THRESHOLD_PX = 10;

interface PlacedPiece {
  uid: number;
  kind: string;
}

interface DragPreview {
  kind: string;
  x: number;
  y: number;
}

function totalOf(kinds: string[]): number {
  return kinds.reduce((sum, kind) => sum + (PIECE_VALUES[kind] ?? 0), 0);
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function PieceChip({ kind }: { kind: string }) {
  return (
    <span className="relative block h-12 w-12">
      <ChessPiece symbol={kind as "P"} />
      <span className="absolute -bottom-1 -right-1 rounded-full bg-stone-800 px-1.5 text-[11px] font-black text-white">
        {faNum(PIECE_VALUES[kind] ?? 0)}
      </span>
    </span>
  );
}

export function BalanceScalePlay({
  slug,
  titleKey,
  introKey,
}: {
  slug: string;
  titleKey: FaKey;
  introKey: FaKey;
}) {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader title={t(titleKey)} subtitle={t(introKey)} />
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

  return <ScaleLoop slug={slug} titleKey={titleKey} mode={mode} onChangeMode={setMode} />;
}

function ScaleLoop({
  slug,
  titleKey,
  mode,
  onChangeMode,
}: {
  slug: string;
  titleKey: FaKey;
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [left, setLeft] = useState<PlacedPiece[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [drag, setDrag] = useState<DragPreview | null>(null);
  const uidRef = useRef(0);
  const panRef = useRef<HTMLDivElement | null>(null);
  const gesture = useRef({
    pointerId: -1,
    kind: "",
    fromUid: null as number | null,
    startX: 0,
    startY: 0,
  });
  const locked = result !== null || submitting;

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles(slug));
    } catch {
      setError(t("common.error"));
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const bank = puzzle ? asStringList(puzzle.position_json.bank).map((s) => s.toUpperCase()) : [];
  const right = puzzle ? asStringList(puzzle.position_json.right).map((s) => s.toUpperCase()) : [];

  function resetForPuzzle() {
    setLeft([]);
    setUsedHints([]);
    setResult(null);
    setDrag(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
    resetForPuzzle();
  }

  const leftKinds = left.map((p) => p.kind);
  const remaining = (kind: string) =>
    bank.filter((k) => k === kind).length - leftKinds.filter((k) => k === kind).length;

  function addPiece(kind: string) {
    if (locked || remaining(kind) <= 0) return;
    uidRef.current += 1;
    setLeft((prev) => [...prev, { uid: uidRef.current, kind }]);
  }

  function removeUid(uid: number) {
    if (locked) return;
    setLeft((prev) => prev.filter((p) => p.uid !== uid));
  }

  function pointInPan(clientX: number, clientY: number): boolean {
    const el = panRef.current;
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    return clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom;
  }

  function onItemPointerDown(kind: string, fromUid: number | null, e: React.PointerEvent) {
    if (locked || e.pointerId === gesture.current.pointerId) return;
    gesture.current = {
      pointerId: e.pointerId,
      kind,
      fromUid,
      startX: e.clientX,
      startY: e.clientY,
    };
  }

  function onContainerPointerMove(e: React.PointerEvent) {
    const g = gesture.current;
    if (g.pointerId === -1 || e.pointerId !== g.pointerId || drag) return;
    if (Math.hypot(e.clientX - g.startX, e.clientY - g.startY) > DRAG_THRESHOLD_PX) {
      setDrag({ kind: g.kind, x: e.clientX, y: e.clientY });
    }
  }

  function onContainerPointerUp(e: React.PointerEvent) {
    const g = gesture.current;
    if (g.pointerId === -1 || e.pointerId !== g.pointerId) return;
    const wasDragging = drag !== null;
    const insidePan = pointInPan(e.clientX, e.clientY);
    gesture.current.pointerId = -1;
    setDrag(null);
    if (locked) return;
    if (!wasDragging) {
      // Tap fallback: bank adds one copy, left pan removes the instance.
      if (g.fromUid === null) addPiece(g.kind);
      else removeUid(g.fromUid);
      return;
    }
    if (insidePan) {
      if (g.fromUid === null) addPiece(g.kind);
    } else if (g.fromUid !== null) {
      removeUid(g.fromUid);
    }
  }

  function onContainerPointerCancel(e: React.PointerEvent) {
    if (e.pointerId !== gesture.current.pointerId) return;
    gesture.current.pointerId = -1;
    setDrag(null);
  }

  async function submit() {
    if (!puzzle || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { pieces: leftKinds },
        mode,
        hints_used: usedHints,
        started_at: startedAt,
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
  const leftTotal = totalOf(leftKinds);
  const rightTotal = totalOf(right);
  const angle = Math.max(-8, Math.min(8, (leftTotal - rightTotal) * 1.5));
  const submittedTotal = result?.detail.submitted_value;
  const targetTotal = result?.detail.target_value;

  return (
    <div
      onPointerMove={onContainerPointerMove}
      onPointerUp={onContainerPointerUp}
      onPointerCancel={onContainerPointerCancel}
    >
      <PageHeader title={t(titleKey)} subtitle={puzzle.prompt_fa} />
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

      <Card>
        <div dir="ltr">
          <div className="relative mx-auto w-full max-w-sm select-none" style={{ touchAction: "pan-y" }}>
            <div className="absolute left-8 right-8 top-4 h-2 rounded-full bg-amber-700 transition-transform" style={{ transform: `rotate(${-angle}deg)` }} />
            <div className="mx-auto h-0 w-0 border-x-[14px] border-t-[20px] border-x-transparent border-t-amber-700" />
            <div className="mt-1 flex items-start justify-between gap-4">
              <div className="flex flex-1 flex-col items-center">
                <p className="text-sm font-black text-stone-700">{t("balance.leftPan")}</p>
                <div
                  ref={panRef}
                  className={`mt-1 flex min-h-[96px] w-full flex-wrap content-start items-start justify-center gap-1 rounded-2xl border-2 border-dashed p-2 ${
                    result ? "border-stone-200 bg-stone-50" : "border-violet-300 bg-violet-50"
                  }`}
                >
                  {left.map((p) => (
                    <button
                      key={p.uid}
                      type="button"
                      aria-label={p.kind}
                      disabled={locked}
                      onPointerDown={(e) => onItemPointerDown(p.kind, p.uid, e)}
                      className="rounded-xl p-1 transition active:bg-violet-200"
                      style={{ touchAction: "none" }}
                    >
                      <PieceChip kind={p.kind} />
                    </button>
                  ))}
                </div>
                <p className="mt-1 text-sm font-bold text-stone-600">
                  {t("balance.leftSide")}: {faNum(leftTotal)}
                </p>
              </div>
              <div className="flex flex-1 flex-col items-center">
                <p className="text-sm font-black text-stone-700">{t("balance.rightPan")}</p>
                <div className="mt-1 flex min-h-[96px] w-full flex-wrap content-start items-start justify-center gap-1 rounded-2xl border-2 border-stone-200 bg-stone-50 p-2">
                  {right.map((kind, i) => (
                    <span key={`${kind}-${i}`} className="rounded-xl p-1">
                      <PieceChip kind={kind} />
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-sm font-bold text-stone-600">
                  {t("balance.rightSide")}: {faNum(rightTotal)}
                </p>
              </div>
            </div>
          </div>
        </div>
        <p className="mt-3 text-center text-xs text-stone-500">{t("balance.howto")}</p>
      </Card>

      {!result ? (
        <div>
          <Card className="mt-3">
            <p className="text-sm font-black">{t("balance.bank")}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {PIECE_ORDER.filter((kind) => bank.includes(kind)).map((kind) =>
                Array.from({ length: remaining(kind) }, (_, i) => (
                  <button
                    key={`${kind}-${i}`}
                    type="button"
                    aria-label={kind}
                    disabled={locked}
                    onPointerDown={(e) => onItemPointerDown(kind, null, e)}
                    className="rounded-2xl border-2 border-stone-200 bg-white p-1 transition active:border-violet-500 active:bg-violet-50"
                    style={{ touchAction: "none" }}
                  >
                    <PieceChip kind={kind} />
                  </button>
                )),
              )}
            </div>
          </Card>
          <div className="mt-3 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setLeft([])} disabled={submitting}>
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
              <p className="text-2xl font-black text-red-600">{faNum(result.detail.wrong.length)}</p>
              <p className="text-xs text-stone-500">{t("play.wrongCount")}</p>
            </div>
          </div>
          <p className="mt-3 text-sm font-bold">
            {t("balance.leftSide")}: {faNum(submittedTotal ?? leftTotal)} / {t("balance.rightSide")}:{" "}
            {faNum(targetTotal ?? rightTotal)}
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

      {drag ? (
        <span
          className="pointer-events-none fixed z-50 block h-14 w-14"
          style={{ left: drag.x, top: drag.y, transform: "translate(-50%, -60%) scale(1.15)" }}
          aria-hidden="true"
        >
          <ChessPiece symbol={drag.kind as "P"} />
        </span>
      ) : null}
    </div>
  );
}
