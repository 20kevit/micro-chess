import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { AttemptResponse, Hint, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { FeedbackText } from "../ui/PageHeader";

export const faNum = (n: number) => n.toLocaleString("fa-IR");

// Full-viewport gameplay shell for Exercise 1 (reusable by future
// time-critical board exercises). The shell is a fixed overlay, so the game
// owns the entire viewport: board + question + timer + submit always fit,
// portrait or landscape, with no page scrolling. correctness/scoring stay
// backend-authoritative; this file only lays out and transports.

export type GameOrientation = "portrait" | "landscape";

/** Pure layout decision: wide screens play side-by-side. Tested. */
export function orientationOf(width: number, height: number): GameOrientation {
  return width > height ? "landscape" : "portrait";
}

/** Cap for very large screens: board never grows past a usable size. */
export const GAME_BOARD_MAX = 600;

/** Pure board fit: largest square inside the area, capped. Tested. */
export function fitSquareSize(areaWidth: number, areaHeight: number, max = GAME_BOARD_MAX): number {
  if (!Number.isFinite(areaWidth) || !Number.isFinite(areaHeight)) return 0;
  return Math.max(0, Math.min(Math.floor(Math.min(areaWidth, areaHeight)), max));
}

/** Ref callback shape for measured game nodes. */
export type DivRef = (node: HTMLDivElement | null) => void;

/** Measures the game root (orientation) and the board area (square size).
 *
 * Callback refs measure on attach, so nodes that mount later (e.g. after
 * the loading branch resolves) are picked up immediately — a mount-once
 * effect would observe nothing and freeze the board at zero. */
export function useGameFit(max = GAME_BOARD_MAX) {
  const nodes = useRef<{ root: HTMLDivElement | null; area: HTMLDivElement | null }>({
    root: null,
    area: null,
  });
  const roRef = useRef<ResizeObserver | null>(null);
  const [metrics, setMetrics] = useState<{ orientation: GameOrientation; size: number }>({
    orientation: "portrait",
    size: 0,
  });
  const update = useCallback(() => {
    const root = nodes.current.root?.getBoundingClientRect();
    const area = nodes.current.area?.getBoundingClientRect();
    if (!root || !area) return;
    setMetrics({
      orientation: orientationOf(root.width, root.height),
      size: fitSquareSize(area.width, area.height, max),
    });
  }, [max]);
  const observe = useCallback(
    (node: HTMLDivElement | null) => {
      if (node && roRef.current) roRef.current.observe(node);
    },
    [],
  );
  const setNode = useCallback(
    (key: "root" | "area") => (node: HTMLDivElement | null) => {
      nodes.current[key] = node;
      observe(node);
      update();
    },
    [observe, update],
  );
  const rootRef = useCallback<DivRef>(
    (node) => setNode("root")(node),
    [setNode],
  );
  const areaRef = useCallback<DivRef>(
    (node) => setNode("area")(node),
    [setNode],
  );
  useEffect(() => {
    if (typeof ResizeObserver === "undefined") {
      update();
      return;
    }
    const ro = new ResizeObserver(update);
    roRef.current = ro;
    observe(nodes.current.root);
    observe(nodes.current.area);
    update();
    return () => {
      ro.disconnect();
      roRef.current = null;
    };
  }, [observe, update]);
  return { rootRef, areaRef, orientation: metrics.orientation, size: metrics.size };
}

export function GameShell({
  title,
  modeKey,
  stat,
  scroll,
  children,
}: {
  title: string;
  modeKey: FaKey;
  /** Optional compact tally shown beside the mode badge (e.g. practice totals). */
  stat?: string;
  /** Only for long summary screens (report). Gameplay itself never scrolls. */
  scroll?: boolean;
  children: ReactNode;
}) {
  // The overlay covers the AppShell chrome; lock background scroll while mounted.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);
  return (
    <div
      className={`fixed inset-0 z-40 flex min-h-0 min-w-0 flex-col bg-[#f6f4ff] ${
        scroll ? "overflow-y-auto" : "overflow-hidden"
      }`}
      dir="rtl"
      data-testid="game-shell"
    >
      <header className="flex h-11 shrink-0 items-center gap-2 px-3">
        <Link
          to="/"
          aria-label={t("common.back")}
          title={t("common.back")}
          className="grid min-h-[44px] min-w-[44px] place-items-center rounded-2xl text-base font-black text-violet-700 active:bg-violet-100"
          style={{ touchAction: "manipulation" }}
        >
          <span aria-hidden="true">→</span>
        </Link>
        <h1 className="min-w-0 flex-1 truncate text-center text-base font-black text-stone-900">{title}</h1>
        {stat ? (
          <span className="shrink-0 text-xs font-bold text-stone-500" dir="ltr">
            {stat}
          </span>
        ) : null}
        <Badge>{t(modeKey)}</Badge>
      </header>
      {children}
    </div>
  );
}

function HintPopover({
  hints,
  usedHints,
  onUse,
  onClose,
}: {
  hints: Hint[];
  usedHints: string[];
  onUse: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-label={t("play.hints")}
      className="absolute start-0 top-full z-30 mt-2 max-h-48 w-64 max-w-[80vw] min-w-0 overflow-y-auto rounded-2xl border-2 border-violet-200 bg-white p-3 shadow-lg"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-black text-stone-800">{t("play.hints")}</p>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("play.clear")}
          className="grid min-h-[44px] min-w-[44px] place-items-center rounded-xl text-base font-black text-stone-500 active:bg-stone-100"
          style={{ touchAction: "manipulation" }}
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      {hints.map((h) => {
        const revealed = usedHints.includes(h.id);
        return revealed ? (
          <p key={h.id} className="mt-1 text-sm text-stone-700">
            {h.text_fa}
          </p>
        ) : (
          <Button key={h.id} variant="ghost" className="mt-1 w-full px-2" onClick={() => onUse(h.id)}>
            {t("play.useHint")}
          </Button>
        );
      })}
    </div>
  );
}

export function QuestionHeader({
  prompt,
  puzzleKey,
  hints,
  usedHints,
  onUseHint,
}: {
  prompt: string;
  /** Remounts the hint button per puzzle so its open state never leaks across. */
  puzzleKey: number | string;
  hints: Hint[];
  usedHints: string[];
  onUseHint: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative shrink-0 px-3 pt-1" data-testid="question">
      <div className="flex min-w-0 items-center gap-2">
        {hints.length > 0 ? (
          <div className="relative shrink-0" key={puzzleKey}>
            <button
              type="button"
              aria-label={t("play.hints")}
              title={t("play.hints")}
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              className="grid h-11 w-11 place-items-center"
              style={{ touchAction: "manipulation" }}
            >
              <span
                aria-hidden="true"
                className="grid h-9 w-9 place-items-center rounded-full border-2 border-violet-200 bg-white text-lg font-black text-violet-700 active:bg-violet-100"
              >
                ؟
              </span>
            </button>
            {open ? (
              <HintPopover
                hints={hints}
                usedHints={usedHints}
                onUse={onUseHint}
                onClose={() => setOpen(false)}
              />
            ) : null}
          </div>
        ) : (
          <span className="w-11 shrink-0" aria-hidden="true" />
        )}
        <p className="min-w-0 flex-1 text-center text-lg font-black leading-8 text-stone-900 sm:text-xl">
          {prompt}
        </p>
        <span className="w-11 shrink-0" aria-hidden="true" />
      </div>
    </div>
  );
}

export function TimerStrip({
  remainingSec,
  correct,
  progress,
}: {
  remainingSec: number;
  correct: number;
  progress: number;
}) {
  return (
    <div
      className="mx-3 mt-1 shrink-0 rounded-2xl border-2 border-violet-200 bg-white px-3 py-1"
      role="timer"
      aria-live="polite"
      aria-label={t("speed.timeLeft")}
      data-testid="timer"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="text-xs font-bold text-stone-600">{t("speed.timeLeft")}</span>
        <span className="text-lg font-black text-violet-700" dir="ltr">
          {faNum(remainingSec)} <span className="text-xs font-bold">{t("common.seconds")}</span>
        </span>
        <Badge>
          {t("play.correctCount")}: {faNum(correct)}
        </Badge>
      </div>
      <div className="mt-1 h-1.5 min-w-0 overflow-hidden rounded-full bg-violet-100" aria-hidden="true">
        <div
          className="h-full rounded-full bg-violet-600 transition-[width]"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
    </div>
  );
}

export function BoardZone({
  areaRef,
  size,
  puzzle,
  selected,
  result,
  disabled,
  onToggle,
  overlay,
}: {
  areaRef: DivRef;
  size: number;
  puzzle: Puzzle;
  selected: string[];
  result: AttemptResponse | null;
  disabled: boolean;
  onToggle: (square: string) => void;
  overlay?: ReactNode;
}) {
  const pieces = fenToPieces(puzzle.fen);
  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong">> = {};
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  } else {
    for (const s of selected) squareStates[s] = "selected";
  }
  return (
    <div ref={areaRef} className="relative min-h-0 min-w-0 flex-1" data-testid="board-zone">
      <div className="absolute inset-0 grid place-items-center">
        <div dir="ltr" data-testid="chessboard" style={{ width: size, height: size }}>
          <ChessBoard
            pieces={pieces}
            onSquarePress={result ? undefined : onToggle}
            squareStates={squareStates}
            disabled={disabled}
          />
        </div>
      </div>
      {overlay}
    </div>
  );
}

/** Floating speed feedback: result + score, no layout impact, auto-dismissed. */
export function SpeedPill({ result }: { result: AttemptResponse }) {
  const tone =
    result.result === "correct"
      ? "border-green-500 bg-green-50 text-green-800"
      : result.result === "partial"
        ? "border-amber-500 bg-amber-50 text-amber-800"
        : "border-red-400 bg-red-50 text-red-700";
  return (
    <div className="pointer-events-none absolute inset-x-0 top-2 z-20 flex justify-center" aria-live="polite">
      <div className={`rounded-full border-2 px-4 py-1 text-sm font-black shadow-md ${tone}`}>
        <FeedbackText feedbackKey={result.feedback_key} /> · {faNum(result.score)} {t("speed.score")}
      </div>
    </div>
  );
}

export function SubmitBar({
  selectedCount,
  emptyHint,
  submitting,
  onSubmit,
  onClear,
}: {
  selectedCount: number;
  emptyHint: string | null;
  submitting: boolean;
  onSubmit: () => void;
  onClear: () => void;
}) {
  return (
    <div className="shrink-0 px-3 pb-3 pt-1" data-testid="submit-bar">
      <p className="mb-1 truncate text-center text-xs font-bold text-stone-600">
        {t("play.selected")}: {faNum(selectedCount)}
        {emptyHint ? ` · ${emptyHint}` : null}
      </p>
      <div className="flex gap-2">
        <Button className="min-w-0 flex-1" onClick={onSubmit} disabled={submitting}>
          {t("play.submit")}
        </Button>
        <Button variant="secondary" onClick={onClear} disabled={submitting}>
          {t("play.clear")}
        </Button>
      </div>
    </div>
  );
}

export function NextBar({ onNext, onRetry }: { onNext: () => void; onRetry: () => void }) {
  return (
    <div className="shrink-0 px-3 pb-3 pt-1" data-testid="next-bar">
      <div className="flex gap-2">
        <Button className="min-w-0 flex-1" onClick={onNext}>
          {t("play.next")}
        </Button>
        <Button variant="secondary" onClick={onRetry}>
          {t("play.retry")}
        </Button>
      </div>
    </div>
  );
}

export function PracticeFeedback({ puzzle, result }: { puzzle: Puzzle; result: AttemptResponse }) {
  const tone =
    result.result === "correct"
      ? "border-green-500 bg-green-50"
      : result.result === "partial"
        ? "border-amber-500 bg-amber-50"
        : "border-red-400 bg-red-50";
  return (
    <div className="shrink-0 px-3" data-testid="feedback">
      <div className={`rounded-2xl border-2 px-3 py-2 ${tone}`}>
        <FeedbackText feedbackKey={result.feedback_key} />
        <p className="mt-1 text-center text-base font-black text-stone-800">
          {faNum(result.score)} {t("speed.score")}
        </p>
        <ul className="mt-1 grid gap-0.5 text-xs font-bold text-stone-700">
          <li>
            <span aria-hidden="true" className="text-green-700">✓ </span>
            {t("piece.legendCorrect")}: {faNum(result.detail.correct.length)}
          </li>
          <li>
            <span aria-hidden="true" className="text-red-600">✕ </span>
            {t("piece.legendWrong")}: {faNum(result.detail.wrong.length)}
          </li>
          <li>
            <span aria-hidden="true" className="text-amber-600">! </span>
            {t("piece.legendMissed")}: {faNum(result.detail.missed.length)}
          </li>
        </ul>
        <p className="mt-1 truncate text-xs font-bold text-stone-700">
          {t("play.correctAnswer")}:{" "}
          <span dir="ltr">{result.detail.correct.concat(result.detail.missed).join("، ") || "—"}</span>
        </p>
        {puzzle.explanation ? (
          <p className="mt-0.5 line-clamp-2 text-xs text-stone-600">
            {t("play.explanation")}: {puzzle.explanation}
          </p>
        ) : null}
      </div>
    </div>
  );
}
